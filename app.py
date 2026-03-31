import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from google import genai
from groq import Groq
import json
import re
import time

# 📱 1. 기본 설정 및 VIP 다크 모드 UI 스타일
st.set_page_config(page_title="AI 실시간 주식 리포트", page_icon="📈", layout="centered")

st.markdown("""
<style>
    /* 전체 배경 및 폰트 */
    .stApp { background-color: #0b0e14; color: #d1d5db; font-family: 'Pretendard', sans-serif; }
    
    /* 섹션 제목 */
    .section-title { font-size: 1.1rem; font-weight: bold; color: #9ca3af; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; }
    
    /* VIP 스타일 카드 */
    .vip-card { background-color: #171c26; border-radius: 12px; padding: 18px; position: relative; border: 1px solid #1f2937; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .card-title { font-size: 0.85rem; color: #6b7280; margin-bottom: 8px; font-weight: 600; }
    .card-value { font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 8px; line-height: 1.3; }
    .card-desc { font-size: 0.85rem; color: #9ca3af; line-height: 1.5; }
    
    /* 최상단 가격 정보 특화 스타일 */
    .top-price-title { font-size: 0.85rem; color: #6b7280; margin-bottom: 4px; }
    .top-price-val { font-size: 1.8rem; font-weight: 800; color: #ffffff; line-height: 1.1; }
    
    /* 텍스트 컬러 */
    .txt-green { color: #10b981 !important; }
    .txt-red { color: #ef4444 !important; }
    .txt-yellow { color: #f59e0b !important; }
    
    /* 신호등 도트 (우측 상단) */
    .dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; position: absolute; top: 18px; right: 18px; }
    .dot-green { background-color: #10b981; box-shadow: 0 0 5px #10b981; }
    .dot-red { background-color: #ef4444; box-shadow: 0 0 5px #ef4444; }
    .dot-yellow { background-color: #f59e0b; box-shadow: 0 0 5px #f59e0b; }
    
    /* 그리드 시스템 */
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }
    
    /* 지지/저항 피벗 박스 스타일 */
    .pivot-box { border-radius: 8px; padding: 12px 0; text-align: center; display: flex; flex-direction: column; justify-content: center; border: 1px solid #2d3748;}
    .pv-title { font-size: 0.75rem; margin-bottom: 4px; opacity: 0.8;}
    .pv-val { font-size: 1.1rem; font-weight: 700; }
    .bg-sup { background-color: rgba(59, 130, 246, 0.15); border-color: rgba(59, 130, 246, 0.4); color: #93c5fd; }
    .bg-piv { background-color: rgba(139, 92, 246, 0.15); border-color: rgba(139, 92, 246, 0.4); color: #c4b5fd; }
    .bg-res { background-color: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
    .bg-ath { background-color: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.4); color: #fcd34d; }
    
    /* AI 시나리오 박스 */
    .ai-row { display: flex; gap: 12px; margin-bottom: 10px; }
    .ai-label { min-width: 80px; font-size: 0.85rem; color: #9ca3af; }
    .ai-text { font-size: 0.9rem; color: #e5e7eb; line-height: 1.6; }
    .scenario-box { border-radius: 8px; padding: 15px; flex: 1; border: 1px solid; }
    .box-bull { background-color: rgba(16, 185, 129, 0.05); border-color: rgba(16, 185, 129, 0.3); }
    .box-bear { background-color: rgba(239, 68, 68, 0.05); border-color: rgba(239, 68, 68, 0.3); }

    /* 매수/매도 뱃지 */
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #10b981; color: #000; }
    .badge-sell { background-color: #ef4444; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# ... (위쪽 import 및 CSS 생략) ...

# 🔍 2. 스마트 검색창 (CSV 기반 자동완성)
@st.cache_data
def load_tickers():
    try:
        # 내 컴퓨터(또는 깃허브)에 있는 CSV 파일을 0.01초 만에 읽어옵니다.
        return pd.read_csv("krx_tickers.csv")
    except FileNotFoundError:
        return pd.DataFrame(columns=["name", "ticker"])

df_tickers = load_tickers()

col_search, col_btn = st.columns([4, 1])
with col_search:
    query = st.text_input("종목 검색", "", placeholder="예: 삼성전자, 반도체, NVDA", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

# 💡 유저님이 설계한 검색 & 선택 로직
if query:
    # 띄어쓰기 무시하고 검색되도록 처리
    clean_query = query.replace(" ", "").upper()
    mask = df_tickers["name"].str.replace(" ", "").str.upper().str.contains(clean_query, na=False)
    results = df_tickers[mask]

    if not results.empty:
        # 검색 결과가 있으면 셀렉트박스로 보여줌
        selected_name = st.selectbox("👇 검색 결과에서 선택하세요", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name # 화면 표시용 이름
    else:
        # CSV에 없는 종목(예: NVDA, AAPL 등 미국주식)이면 입력한 그대로 야후에 넘김
        symbol = query.upper()
        search_query = query.upper()
else:
    # 아무것도 안 쳤을 때 기본값
    symbol = "396500.KS"
    search_query = "TIGER 반도체TOP10"

# ... (이하 🛡️ 3. 데이터 로드 및 UI 렌더링 코드는 기존과 완전 동일) ...

# 🛡️ 3. 데이터 로드 (캐싱 + 상세 정보)
@st.cache_data(ttl=600)
def load_stock_data(sym):
    df = None
    info = {}
    for i in range(3):
        try:
            tkr = yf.Ticker(sym)
            df = tkr.history(period="1y", interval="1d")
            info = tkr.info
            if df is not None and not df.empty: break
        except Exception: time.sleep(1)
    
    if df is not None and not df.empty:
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA50'] = df['Close'].rolling(50).mean()
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
        
        return df, info
    return None, {}

# 🤖 4. 하이브리드 AI 엔진
@st.cache_data(ttl=600)
def get_ai_scenarios(q, curr, rsi, macd):
    prompt = f"""종목:{q}, 현재가:{curr}, RSI:{rsi:.1f}. 
    반드시 JSON 포맷으로 작성. 
    항목:
    decision ('매수', '매도', '관망' 중 1개),
    short_term (단기 전망 및 박스권 예상 2문장 내외), 
    mid_term (중장기 펀더멘탈 및 시황 전망 2문장 내외), 
    bull (상승 시나리오 요약 및 이유 2문장 내외), 
    bear (하락 시나리오 요약 및 이유 2문장 내외). 
    한국어 전문 애널리스트 톤으로 작성."""
    
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except: pass

    gemini_keys = [st.secrets.get("GEMINI_API_KEY_1"), st.secrets.get("GEMINI_API_KEY_2")]
    for k in [gk for gk in gemini_keys if gk]:
        try:
            client = genai.Client(api_key=k)
            res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            jt = re.sub(r'```[a-zA-Z]*\n|```', '', res.text).strip()
            return json.loads(jt[jt.find('{'):jt.rfind('}')+1])
        except: continue
    
    return {"decision":"관망", "short_term":"API 점검 중입니다.", "mid_term":"잠시 후 갱신해 주세요.", "bull":"-", "bear":"-"}

# 📊 5. 메인 UI 렌더링
with st.spinner("VIP 리포트 데이터 수집 중..."):
    df, info = load_stock_data(symbol)
    
    if df is not None and not df.empty:
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        curr_price = float(last['Close'])
        prev_price = float(prev['Close'])
        change_val = curr_price - prev_price
        change_pct = (change_val / prev_price) * 100
        
        high_52 = float(df['High'].max())
        low_52 = float(df['Low'].min())
        drop_from_high = ((curr_price - high_52) / high_52) * 100
        
        target_price = info.get('targetMeanPrice', 0)
        target_pct = ((target_price - curr_price)/curr_price)*100 if target_price else 0
        
        rsi_val = last['RSI'] if not pd.isna(last['RSI']) else 50
        macd_val = last['MACD'] if not pd.isna(last['MACD']) else 0

        # 💡 [핵심 버그 수정] UI 그리기 전에 AI 데이터를 먼저 불러옵니다!
        ai_data = get_ai_scenarios(search_query, curr_price, rsi_val, macd_val)
        decision = ai_data.get('decision', '관망')
        badge_cls = "badge-buy" if decision == "매수" else ("badge-sell" if decision == "매도" else "badge-hold")
        
        # --- UI 시작 ---
        st.markdown(f"""
            <span class="badge {badge_cls}">{decision}</span>
            <h2 style="margin:0;">{search_query} <span style='font-size:1rem;color:#6b7280;font-weight:normal;'>{symbol}</span></h2>
        """, unsafe_allow_html=True)
        
        # [상단 요약]
        c_color = "txt-red" if change_val < 0 else "txt-green"
        c_sign = "" if change_val < 0 else "+"
        
        st.markdown(f"""
        <div class="grid-2" style="margin-bottom: 30px;">
            <div>
                <div class="top-price-title">정규장 종가</div>
                <div class="top-price-val">{format_price(curr_price, symbol)}</div>
                <div style="font-size:0.95rem; margin-top:5px;" class="{c_color}">
                    {c_sign}{format_price(change_val, symbol)} / {c_sign}{change_pct:.2f}%
                </div>
            </div>
            <div>
                <div class="top-price-title">52주 고점 / 저점</div>
                <div class="top-price-val" style="font-size:1.4rem;">{format_price(high_52, symbol)} / {format_price(low_52, symbol)}</div>
                <div style="font-size:0.9rem; margin-top:5px;" class="txt-red">고점 대비 {drop_from_high:.1f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # [목표가 및 실적]
        st.markdown(f"""
        <div class="grid-2">
            <div>
                <div class="top-price-title">애널리스트 목표가 (평균)</div>
                <div class="top-price-val" style="font-size:1.3rem;">{format_price(target_price, symbol) if target_price else "데이터 없음"}</div>
                <div style="font-size:0.9rem;" class="{"txt-green" if target_pct > 0 else "txt-red"}">
                    {"+" if target_pct > 0 else ""}{target_pct:.1f}% 상승여력
                </div>
            </div>
            <div>
                <div class="top-price-title">섹터 / 산업군</div>
                <div class="top-price-val" style="font-size:1.1rem; color:#d1d5db;">{info.get('sector', 'ETF/정보없음')}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # [추세 분석]
        st.markdown("<div class='section-title'>추세 분석 · 이동평균</div>", unsafe_allow_html=True)
        
        ma_status = "단기 상승 추세" if curr_price > last['MA20'] else "단기 하락 추세"
        ma_color = "dot-green" if curr_price > last['MA20'] else "dot-red"
        
        trend_status = "강세 유지" if curr_price > last['MA50'] else "약세 지속"
        trend_color = "dot-green" if curr_price > last['MA50'] else "dot-red"
        
        st.markdown(f"""
        <div class="grid-2">
            <div class="vip-card">
                <span class="dot {ma_color}"></span>
                <div class="card-title">이동평균선 (20일)</div>
                <div class="card-value">{ma_status}</div>
                <div class="card-desc">현재가 {format_price(curr_price, symbol)}가 20일선({format_price(last['MA20'], symbol)}) {"위에 위치하며 지지" if curr_price > last['MA20'] else "아래에 위치하며 저항"}받는 상태</div>
            </div>
            <div class="vip-card">
                <span class="dot {trend_color}"></span>
                <div class="card-title">추세 방향 (50일)</div>
                <div class="card-value">{trend_status}</div>
                <div class="card-desc">중기 50일선 기준 {"상승 흐름 유지 중" if curr_price > last['MA50'] else "조정 국면 지속 중"}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # [모멘텀 지표]
        st.markdown("<div class='section-title'>모멘텀 지표</div>", unsafe_allow_html=True)
        
        if rsi_val > 70: r_txt, r_dot, r_desc = "과매수 구간", "dot-red", "RSI 과매수 수준. 단기 고점 도달로 인한 차익 실현 주의."
        elif rsi_val < 30: r_txt, r_dot, r_desc = "과매도 구간", "dot-green", "RSI 과매도 수준. 단기 기술적 반등 가능성 존재."
        else: r_txt, r_dot, r_desc = "중립 수준", "dot-yellow", "방향성 탐색 중. 뚜렷한 과열이나 침체 없는 상태."
        
        sig_val = last['MACD_Signal'] if not pd.isna(last['MACD_Signal']) else 0
        
        m_txt = "매수 신호 (골든크로스)" if macd_val > sig_val else "매도 신호 (데드크로스)"
        m_dot = "dot-green" if macd_val > sig_val else "dot-red"
        
        st.markdown(f"""
        <div class="grid-2">
            <div class="vip-card">
                <span class="dot {r_dot}"></span>
                <div class="card-title">RSI (14)</div>
                <div class="card-value">RSI {rsi_val:.0f} — {r_txt}</div>
                <div class="card-desc">{r_desc}</div>
            </div>
            <div class="vip-card">
                <span class="dot {m_dot}"></span>
                <div class="card-title">MACD (12, 26)</div>
                <div class="card-value">{m_txt}</div>
                <div class="card-desc">{"MACD가 시그널선을 상향 돌파하며 모멘텀 강화" if macd_val > sig_val else "MACD가 시그널선을 하향 이탈하며 하방 압력 존재"}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # [주요 지지/저항]
        st.markdown("<div class='section-title'>주요 지지 / 저항 레벨</div>", unsafe_allow_html=True)
        piv = (float(last['High']) + float(last['Low']) + curr_price) / 3
        s1 = 2 * piv - float(last['High'])
        s2 = piv - (float(last['High']) - float(last['Low']))
        r1 = 2 * piv - float(last['Low'])
        r2 = piv + (float(last['High']) - float(last['Low']))
        
        st.markdown(f"""
        <div class="grid-3">
            <div class="pivot-box bg-sup"><div class="pv-title">지지 2</div><div class="pv-val">{format_price(s2, symbol)}</div></div>
            <div class="pivot-box bg-sup"><div class="pv-title">강한 지지 1</div><div class="pv-val">{format_price(s1, symbol)}</div></div>
            <div class="pivot-box bg-piv"><div class="pv-title">피벗 (중심)</div><div class="pv-val">{format_price(piv, symbol)}</div></div>
        </div>
        <div class="grid-3">
            <div class="pivot-box bg-res"><div class="pv-title">저항 1</div><div class="pv-val">{format_price(r1, symbol)}</div></div>
            <div class="pivot-box bg-res"><div class="pv-title">강한 저항 2</div><div class="pv-val">{format_price(r2, symbol)}</div></div>
            <div class="pivot-box bg-ath"><div class="pv-title">52주 고점</div><div class="pv-val">{format_price(high_52, symbol)}</div></div>
        </div>
        """, unsafe_allow_html=True)

        # [AI 리포트 렌더링]
        st.markdown("<div class='section-title'>투자 전망 및 시나리오 (AI 전문 분석)</div>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="vip-card" style="margin-bottom:15px; padding:20px;">
            <div class="ai-row">
                <div class="ai-label">단기 (1~2주)</div>
                <div class="ai-text">{ai_data.get('short_term', '분석 중...')}</div>
            </div>
            <div style="height:1px; background:#1f2937; margin:15px 0;"></div>
            <div class="ai-row">
                <div class="ai-label">중기 (1~3개월)</div>
                <div class="ai-text">{ai_data.get('mid_term', '분석 중...')}</div>
            </div>
        </div>
        
        <div class="grid-2">
            <div class="scenario-box box-bull">
                <div style="color:#10b981; font-weight:bold; margin-bottom:8px;">🟢 강세 시나리오</div>
                <div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bull', '데이터 부족')}</div>
            </div>
            <div class="scenario-box box-bear">
                <div style="color:#ef4444; font-weight:bold; margin-bottom:8px;">🔴 약세 시나리오</div>
                <div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bear', '데이터 부족')}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("Data: Yahoo Finance | Analytics Engine: Python TA & AI Hybrid (Groq/Gemini)")

    else:
        st.error("데이터를 가져오지 못했습니다. 종목 코드를 확인하거나 잠시 후 시도해주세요.")
