import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# 📱 기본 설정 (넓은 화면 사용)
st.set_page_config(page_title="AI 주식 대시보드", page_icon="📊", layout="centered")

# --- 커스텀 CSS (모바일 앱 느낌의 다크 테마 카드) ---
st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: bold; }
    .stAlert { border-radius: 10px; }
    .small-font { font-size: 0.9rem; color: #a0aec0; }
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

# --- 상단 검색 및 타이틀 ---
st.markdown("<h2 style='text-align: center;'>📊 AI 실시간 애널리스트 리포트</h2>", unsafe_allow_html=True)
# --- 기존 코드 ---
# search_query = st.text_input("종목명/티커 검색", "ALAB")
# symbol = SYMBOL_MAP.get(search_query.upper(), search_query)

# --- ✨ 수정할 코드 (검색 버튼 추가) ---
col_search, col_btn = st.columns([4, 1]) # 입력창과 버튼 비율을 4:1로!
with col_search:
    search_query = st.text_input("종목명/티커 검색 (예: 삼성전자, NVDA)", "ALAB")
with col_btn:
    st.write("") # 간격 맞추기용 빈칸
    st.write("")
    st.button("🔄 갱신") # 이 버튼을 누르면 글자가 안 바뀌어도 무조건 최신화됨!

symbol = SYMBOL_MAP.get(search_query.upper(), search_query)

# --- 데이터 로드 및 지표 계산 ---
with st.spinner("실시간 주가 및 보조지표 분석 중... 🚀"):
    df = yf.download(symbol, period="1y", progress=False)

if df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다.")
else:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    # 이동평균
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # 볼린저 밴드
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

    # --- 상태 텍스트 판단 ---
    ma_txt = "정배열 상승 추세" if curr_price > last['MA20'] > last['MA50'] else ("단기 하락 추세" if curr_price < last['MA20'] else "방향성 탐색")
    rsi_txt = "과매도 구간" if float(last['RSI']) < 40 else ("과매수 구간" if float(last['RSI']) > 70 else "중립 구간")
    macd_txt = "강세 신호" if last['MACD'] > last['Signal'] else "약세 신호"
    vol_txt = "거래량 증가" if curr_vol > avg_vol * 1.2 else "거래량 감소/평이"
    bb_txt = "하단 근접" if curr_price < last['BB_Lower'] * 1.05 else ("상단 돌파" if curr_price > last['BB_Upper'] * 0.95 else "밴드 내 횡보")

    # ==========================================
    # 🖥️ UI 렌더링 (2번째 이미지 포맷 맞춤)
    # ==========================================
    
    # 1. 상단 기본 정보
    c1, c2 = st.columns(2)
    c1.metric("정규장 종가", f"{c}{curr_price:,.2f}", f"{change_val:+,.2f} ({change_pct:+.2f}%)")
    c2.metric("52주 고점 / 저점", f"{c}{high_52:,.2f} / {c}{low_52:,.2f}", f"고점 대비 {((curr_price-high_52)/high_52)*100:.1f}%", delta_color="inverse")
    
    st.markdown("---")

    # 2. 추세 & 모멘텀 (2x2 그리드)
    st.subheader("📊 추세 및 모멘텀 분석")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**📉 이동평균선 (20/50일)**\n\n### {ma_txt}\n\n20일선: {c}{float(last['MA20']):,.2f}\n\n50일선: {c}{float(last['MA50']):,.2f}")
        st.success(f"**📈 RSI (14)**\n\n### 약 {float(last['RSI']):.0f} - {rsi_txt}\n\n현재 매수/매도 강도를 나타냅니다.")
    with col2:
        st.warning(f"**📊 거래량 패턴**\n\n### {vol_txt}\n\n최근 20일 평균 대비 거래량 수준입니다.")
        st.error(f"**🎯 MACD / 볼린저밴드**\n\n### {macd_txt} / {bb_txt}\n\nMACD: {float(last['MACD']):.2f}\n\n밴드 하단: {c}{float(last['BB_Lower']):,.2f}")

    st.markdown("---")

    # 3. 주요 지지 / 저항 레벨 (5개 박스)
    st.subheader("🎯 주요 지지 / 저항 레벨")
    pivot = (float(last['High']) + float(last['Low']) + curr_price) / 3
    res1 = (2 * pivot) - float(last['Low'])
    res2 = pivot + (float(last['High']) - float(last['Low']))
    sup1 = (2 * pivot) - float(last['High'])
    sup2 = pivot - (float(last['High']) - float(last['Low']))

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.error(f"지 2\n\n**{c}{sup2:,.0f}**")
    s2.error(f"지지 1\n\n**{c}{sup1:,.0f}**")
    s3.secondary(f"피벗\n\n**{c}{pivot:,.0f}**")
    s4.success(f"저항 1\n\n**{c}{res1:,.0f}**")
    s5.success(f"저 2\n\n**{c}{res2:,.0f}**")

    st.markdown("---")

    # 4. AI 투자 전망 및 시나리오 (API 호출)
    st.subheader("🤖 AI 투자 전망 및 시나리오 분석")
    
    prompt = f"""
    너는 최고 수준의 월가 애널리스트야. 다음 '{search_query}' 종목의 실시간 기술적 지표를 바탕으로 핵심만 브리핑해.
    
    - 현재가: {curr_price} / 20일선: {float(last
