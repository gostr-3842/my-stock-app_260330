import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai
import json
import re

# 📱 기본 설정 (모바일 최적화)
st.set_page_config(page_title="AI 주식 대시보드", page_icon="📊", layout="centered")

# ==========================================
# 🎨 영혼을 갈아넣은 모바일 앱 UI (CSS)
# ==========================================
st.markdown("""
<style>
    /* 전체 배경을 어둡게 (다크모드 느낌) */
    .stApp { background-color: #0e1117; color: #ffffff; }
    
    /* 카드 공통 스타일 */
    .card { background-color: #1a1c24; border-radius: 12px; padding: 15px; margin-bottom: 15px; border: 1px solid #2d303e; }
    
    /* 2단 그리드 (폰에서도 무조건 2칸으로 쪼개기) */
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 15px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
    
    /* 텍스트 스타일 */
    .title-sub { font-size: 0.85rem; color: #8b949e; margin-bottom: 5px; }
    .val-main { font-size: 1.2rem; font-weight: 700; color: #ffffff; }
    .val-sub { font-size: 0.9rem; margin-top: 5px; }
    
    /* 상태 색상 텍스트 */
    .red-txt { color: #ff4b4b; }
    .green-txt { color: #00d26a; }
    .gray-txt { color: #a0aec0; }
    
    /* 지지/저항 박스 스타일 */
    .box-sup { background-color: rgba(0, 210, 106, 0.1); border: 1px solid #00d26a; border-radius: 8px; padding: 10px; text-align: center; }
    .box-res { background-color: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; border-radius: 8px; padding: 10px; text-align: center; }
    .box-piv { background-color: rgba(255, 170, 0, 0.1); border: 1px solid #ffaa00; border-radius: 8px; padding: 10px; text-align: center; }
    
    /* 판정 뱃지 */
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #00d26a; color: #000; }
    .badge-sell { background-color: #ff4b4b; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🧠 Gemini API 설정
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    st.error("⚠️ API 키가 설정되지 않았습니다.")

SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS", "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "NVDA": "NVDA", "ALAB": "ALAB", "META": "META", "MSFT": "MSFT"
}

# 🔍 검색창
col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명/티커 검색", "TIGER 반도체TOP10", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

clean_query = search_query.replace(" ", "").upper()
clean_map = {key.replace(" ", "").upper(): value for key, value in SYMBOL_MAP.items()}
symbol = clean_map.get(clean_query, search_query)

# 📈 데이터 로드
with st.spinner("데이터 분석 및 AI 리포트 생성 중... 🚀"):
    df = yf.download(symbol, period="1y", progress=False)

if df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다.")
else:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    # 지표 계산
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)

    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    curr_price = float(last['Close'])
    prev_price = float(prev['Close'])
    change_val = curr_price - prev_price
    change_pct = (change_val / prev_price) * 100
    high_52 = float(df['High'].max())
    low_52 = float(df['Low'].min())
    curr_vol = float(last['Volume'])
    avg_vol = float(df['Volume'].rolling(20).mean().iloc[-1])
    
    c = "₩" if ".KS" in symbol or ".KQ" in symbol else "$"

    # 색상 결정
    color_class = "red-txt" if change_val < 0 else "green-txt"
    sign = "+" if change_val > 0 else ""

    # ==========================================
    # 🤖 AI 분석 요청 (JSON 포맷 강제 + 모델 자동 탐색)
    # ==========================================
    prompt = f"""
    너는 최고 수준의 애널리스트야. '{search_query}' 종목 데이터를 분석해.
    현재가: {curr_price}, 20일선: {float(last['MA20'])}, RSI: {float(last['RSI'])}, MACD: {float(last['MACD'])}
    
    반드시 아래 JSON 형식으로만 응답해. (다른 말은 절대 쓰지 마)
    {{
      "decision": "매수",
      "short_term": "단기 전망 1줄",
      "mid_term": "중기 전망 1줄",
      "bull": "강세 시나리오 1줄",
      "bear": "약세 시나리오 1줄"
    }}
    """
    
    ai_data = {"decision": "분석중", "short_term": "-", "mid_term": "-", "bull": "-", "bear": "-"}
    
    try:
        # 💡 치트키: 구글 서버에 접속해서 '현재 내 API 키로 쓸 수 있는' 모델 목록을 자동 검색!
        valid_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        
        if not valid_models:
            raise ValueError("사용 가능한 제미나이 모델이 없습니다. API 키 상태를 확인해주세요.")
            
        # 검색된 모델 중 가장 첫 번째 모델을 자동으로 선택해서 쓴다!
        auto_model_name = valid_models[0]
        model_stable = genai.GenerativeModel(auto_model_name)
        
        res = model_stable.generate_content(prompt)
        
        # 💡 AI가 앞뒤로 헛소리를 섞어놔도, '{' 부터 '}' 까지만 정확히 파내는 수술 작업
        clean_text = res.text.replace('```json', '').replace('```JSON', '').replace('```', '').strip()
        start_idx = clean_text.find('{')
        end_idx = clean_text.rfind('}') + 1
        
        if start_idx != -1 and end_idx != 0:
            clean_text = clean_text[start_idx:end_idx]
            ai_data = json.loads(clean_text)
        else:
            raise ValueError("JSON 형식을 찾을 수 없음")
            
    except Exception as e:
        # 에러가 나면 숨기지 않고 화면에 띄워서 우리가 볼 수 있게 만듦
        st.error(f"⚠️ AI 분석 에러 원인: {e}")
        if 'valid_models' in locals():
            st.info(f"💡 현재 사용 가능한 모델 목록: {valid_models}")

    # 뱃지 색상 설정
    badge_cls = "badge-buy" if ai_data['decision'] == "매수" else ("badge-sell" if ai_data['decision'] == "매도" else "badge-hold")
    
    # ==========================================
    # 🖥️ 화면 렌더링 (HTML/CSS 주입)
    # ==========================================
    
    # [1] 타이틀 & 뱃지
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <span class="badge {badge_cls}">{ai_data['decision']}</span>
            <h2 style="margin: 0; padding: 0;">{search_query}</h2>
            <div class="title-sub">{symbol} | 분석일: {datetime.now().strftime('%Y.%m.%d')}</div>
        </div>
    """, unsafe_allow_html=True)

    # [2] 핵심 가격 정보 (그리드)
    st.markdown(f"""
        <div class="grid-2">
            <div class="card" style="margin-bottom:0;">
                <div class="title-sub">정규장 종가</div>
                <div class="val-main">{c}{curr_price:,.0f}</div>
                <div class="val-sub {color_class}">{sign}{change_val:,.0f} ({sign}{change_pct:.2f}%)</div>
            </div>
            <div class="card" style="margin-bottom:0;">
                <div class="title-sub">52주 고점 / 저점</div>
                <div class="val-main">{c}{high_52:,.0f} / {c}{low_52:,.0f}</div>
                <div class="val-sub red-txt">고점 대비 {((curr_price-high_52)/high_52)*100:.1f}%</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # [3] 추세 및 모멘텀 (2x2 그리드)
    st.markdown("#### 📊 추세 및 모멘텀 지표")
    
    ma_txt = "상승 추세" if curr_price > last['MA20'] else "단기 하락"
    rsi_txt = "과매도" if float(last['RSI']) < 40 else ("과매수" if float(last['RSI']) > 70 else "중립")
    rsi_color = "green-txt" if float(last['RSI']) < 40 else "gray-txt"
    
    st.markdown(f"""
        <div class="grid-2">
            <div class="card">
                <div class="title-sub">이동평균 (20/50일)</div>
                <div class="val-main">{ma_txt}</div>
                <div class="title-sub" style="margin-top:8px;">20일선: {c}{float(last['MA20']):,.0f}</div>
            </div>
            <div class="card">
                <div class="title-sub">RSI (14)</div>
                <div class="val-main {rsi_color}">RSI {float(last['RSI']):.0f} ({rsi_txt})</div>
                <div class="title-sub" style="margin-top:8px;">매수/매도 강도</div>
            </div>
            <div class="card">
                <div class="title-sub">거래량 패턴</div>
                <div class="val-main">{"거래량 급증" if curr_vol > avg_vol*1.5 else "평이함"}</div>
                <div class="title-sub" style="margin-top:8px;">전일비: {curr_vol/avg_vol*100:.0f}% 수준</div>
            </div>
            <div class="card">
                <div class="title-sub">MACD / 볼린저밴드</div>
                <div class="val-main">{"강세 전환" if last['MACD'] > last['Signal'] else "약세 지속"}</div>
                <div class="title-sub" style="margin-top:8px;">하단: {c}{float(last['BB_Lower']):,.0f}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # [4] 지지 저항 레벨 (2줄 그리드)
    st.markdown("#### 🎯 주요 지지 / 저항 레벨")
    pivot = (float(last['High']) + float(last['Low']) + curr_price) / 3
    res1 = (2 * pivot) - float(last['Low'])
    res2 = pivot + (float(last['High']) - float(last['Low']))
    sup1 = (2 * pivot) - float(last['High'])
    sup2 = pivot - (float(last['High']) - float(last['Low']))

    st.markdown(f"""
        <div class="grid-3">
            <div class="box-sup"><div class="title-sub">강한 지지</div><div class="val-main">{c}{sup2:,.0f}</div></div>
            <div class="box-sup"><div class="title-sub">지지 1</div><div class="val-main">{c}{sup1:,.0f}</div></div>
            <div class="box-piv"><div class="title-sub">피벗(기준)</div><div class="val-main">{c}{pivot:,.0f}</div></div>
        </div>
        <div class="grid-3" style="margin-bottom:20px;">
            <div class="box-res"><div class="title-sub">저항 1</div><div class="val-main">{c}{res1:,.0f}</div></div>
            <div class="box-res"><div class="title-sub">저항 2</div><div class="val-main">{c}{res2:,.0f}</div></div>
            <div class="box-piv"><div class="title-sub">52주 고점</div><div class="val-main">{c}{high_52:,.0f}</div></div>
        </div>
    """, unsafe_allow_html=True)

    # [5] 투자 전망 & 시나리오 (AI 결과 출력)
    st.markdown("#### 🤖 AI 투자 전망 및 시나리오")
    st.markdown(f"""
        <div class="card">
            <div class="title-sub">단기 (1~2주)</div>
            <div style="font-size:0.95rem; margin-bottom:10px;">{ai_data['short_term']}</div>
            <div class="title-sub">중기 (1~3개월)</div>
            <div style="font-size:0.95rem;">{ai_data['mid_term']}</div>
        </div>
        <div class="grid-2">
            <div class="box-sup" style="text-align:left;">
                <div class="green-txt" style="font-weight:bold; margin-bottom:5px;">🟢 강세 시나리오</div>
                <div style="font-size:0.85rem;">{ai_data['bull']}</div>
            </div>
            <div class="box-res" style="text-align:left;">
                <div class="red-txt" style="font-weight:bold; margin-bottom:5px;">🔴 약세 시나리오</div>
                <div style="font-size:0.85rem;">{ai_data['bear']}</div>
            </div>
        </div>
    """, unsafe_allow_html=True)
