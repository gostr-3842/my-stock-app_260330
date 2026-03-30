import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from google import genai # 👈 구글 최신 간판으로 교체!
from groq import Groq
import json
import re
import time

# 📱 1. 기본 설정 및 UI 스타일
st.set_page_config(page_title="AI 실시간 주식 리포트", page_icon="📈", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    .card { background-color: #1a1c24; border-radius: 12px; padding: 15px; margin-bottom: 15px; border: 1px solid #2d303e; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
    .title-sub { font-size: 0.85rem; color: #8b949e; margin-bottom: 5px; }
    .val-main { font-size: 1.2rem; font-weight: 700; color: #ffffff; }
    .val-sub { font-size: 0.9rem; margin-top: 5px; }
    .red-txt { color: #ff4b4b; }
    .green-txt { color: #00d26a; }
    .box-sup { background-color: rgba(0, 210, 106, 0.1); border: 1px solid #00d26a; border-radius: 8px; padding: 10px; text-align: center; }
    .box-res { background-color: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; border-radius: 8px; padding: 10px; text-align: center; }
    .box-piv { background-color: rgba(255, 170, 0, 0.1); border: 1px solid #ffaa00; border-radius: 8px; padding: 10px; text-align: center; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #00d26a; color: #000; }
    .badge-sell { background-color: #ff4b4b; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🔍 2. 종목 검색 설정
SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS", "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "NVDA": "NVDA", "ALAB": "ALAB", "META": "META", "MSFT": "MSFT"
}

col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명/티커 검색", "TIGER 반도체TOP10", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

clean_query = search_query.replace(" ", "").upper()
clean_map = {key.replace(" ", "").upper(): value for key, value in SYMBOL_MAP.items()}
symbol = clean_map.get(clean_query, search_query)

# 🛡️ [캐싱 적용] 1. 야후 파이낸스 데이터 10분 동안 저장
@st.cache_data(ttl=600)
def load_stock_data(sym):
    df = None
    for i in range(3):
        try:
            df = yf.download(sym, period="1y", interval="1d", progress=False, timeout=10)
            if df is not None and not df.empty:
                break
        except Exception:
            time.sleep(1)
    
    if df is not None and not df.empty:
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close'])
        return df
    return None

# 🛡️ [캐싱 적용] 2. 하이브리드 AI 분석 10분 동안 저장 (최신 SDK 적용)
@st.cache_data(ttl=600)
def get_hybrid_analysis(q, curr, ma20, rsi, macd):
    prompt = f"종목:{q},가:{curr},20선:{ma20},RSI:{rsi},MACD:{macd}. JSON: decision(매수/매도/관망), short_term, mid_term, bull, bear. 한국어 답변."
    
    # [Groq 시도]
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            groq_client = Groq(api_key=groq_key)
            completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-specdec",
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except: pass

    # [Gemini 시도 - 최신 구글 genai 클라이언트 방식]
    gemini_keys = [st.secrets.get("GEMINI_API_KEY_1"), st.secrets.get("GEMINI_API_KEY_2")]
    for k in [gk for gk in gemini_keys if gk]:
        try:
            client = genai.Client(api_key=k)
            for m_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                try:
                    res = client.models.generate_content(
                        model=m_name,
                        contents=prompt,
                    )
                    jt = re.sub(r'```[a-zA-Z]*\n|```', '', res.text).strip()
                    return json.loads(jt[jt.find('{'):jt.rfind('}')+1])
                except: continue
        except: continue
    return None

# 📊 3. 메인 로직 실행
with st.spinner(f"'{symbol}' AI 리포트 생성 중..."):
    df = load_stock_data(symbol)
            
    if df is not None:
        # 지표 계산
        df['MA20'] = df['Close'].rolling(20).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        
        last = df.iloc[-1]
        curr_price = float(last['Close'])
        prev_price = float(df.iloc[-2]['Close'])
        change_pct = ((curr_price - prev_price) / prev_price) * 100
        
        # AI 호출
        ai_res = get_hybrid_analysis(search_query, curr_price, float(last['MA20']), float(last['RSI']), float(last['MACD']))
        if not ai_res:
            ai_res = {"decision":"확인불가", "short_term":"API 점검 중", "mid_term":"잠시 후 다시 시도해 주세요", "bull":"-", "bear":"-"}

        # 🖥️ 4. UI 렌더링
        badge_cls = "badge-buy" if ai_res['decision'] == "매수" else ("badge-sell" if ai_res['decision'] == "매도" else "badge-hold")
        st.markdown(f'<span class="badge {badge_cls}">{ai_res["decision"]}</span><h2 style="margin:0;">{search_query}</h2>', unsafe_allow_html=True)
        st.markdown(f'<div class="title-sub">{symbol} | {datetime.now().strftime("%Y.%m.%d")}</div>', unsafe_allow_html=True)

        st.markdown(f"""
            <div class="grid-2">
                <div class="card">
                    <div class="title-sub">정규장 종가</div>
                    <div class="val-main">₩{curr_price:,.0f}</div>
                    <div class="val-sub {"red-txt" if change_pct < 0 else "green-txt"}">{change_pct:+.2f}%</div>
                </div>
                <div class="card">
                    <div class="title-sub">52주 최고점</div>
                    <div class="val-main">₩{float(df["High"].max()):,.0f}</div>
                    <div class="val-sub red-txt">전고점대비 {((curr_price-float(df["High"].max()))/float(df["High"].max()))*100:.1f}%</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="grid-2">
                <div class="card">
                    <div class="title-sub">이동평균 (20일)</div>
                    <div class="val-main">{"상승" if curr_price > last['MA20'] else "하락"}</div>
                    <div class="title-sub">기준가: ₩{last['MA20']:,.0f}</div>
                </div>
                <div class="card">
                    <div class="title-sub">RSI (14) / 강도</div>
                    <div class="val-main">RSI {last['RSI']:.0f}</div>
                    <div class="title-sub">{"과매도(매수기회)" if last['RSI'] < 40 else ("과매수(주의)" if last['RSI'] > 70 else "중립")}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        piv = (float(last['High']) + float(last['Low']) + curr_price) / 3
        st.markdown(f"""
            <div class="grid-3">
                <div class="box-sup"><div class="title-sub">지지선</div><div class="val-main">₩{(2*piv-last['High']):,.0f}</div></div>
                <div class="box-piv"><div class="title-sub">피벗(중심)</div><div class="val-main">₩{piv:,.0f}</div></div>
                <div class="box-res"><div class="title-sub">저항선</div><div class="val-main">₩{(2*piv-last['Low']):,.0f}</div></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class="card">
                <div class="title-sub">AI 애널리스트 리포트</div>
                <div style="font-size:0.95rem; line-height:1.6;">
                    <b>단기 전망:</b> {ai_res['short_term']}<br>
                    <b>중기 전망:</b> {ai_res['mid_term']}
                </div>
            </div>
            <div class="grid-2">
                <div class="box-sup" style="text-align:left;"><b class="green-txt">🟢 강세 요인</b><br><span style="font-size:0.85rem;">{ai_res['bull']}</span></div>
                <div class="box-res" style="text-align:left;"><b class="red-txt">🔴 약세 요인</b><br><span style="font-size:0.85rem;">{ai_res['bear']}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        st.caption("Data: Yahoo Finance | AI: Groq & Gemini Hybrid Engine (업데이트 주기: 10분)")
    else:
        st.error("❌ 야후 파이낸스 서버가 일시적으로 응답하지 않습니다.")
        st.warning("야후의 접속 제한(Too Many Requests)이 걸린 상태일 수 있습니다. 10분 후에 다시 시도해 주세요.")
