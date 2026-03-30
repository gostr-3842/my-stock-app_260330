import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# 📱 기본 설정
st.set_page_config(page_title="AI 주식 대시보드", page_icon="📊", layout="centered")

# --- 커스텀 CSS (모바일 뷰 최적화) ---
st.markdown("""
<style>
    div[data-testid="stMetricValue"] { font-size: 1.8rem; font-weight: bold; }
    .stAlert { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# 🧠 Gemini API 설정
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash')
except:
    st.error("⚠️ API 키가 설정되지 않았습니다. 앱 설정의 Secrets를 확인해주세요.")

# --- 종목 코드 사전 ---
SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS", "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "NVDA": "NVDA", "ALAB": "ALAB", "META": "META", "MSFT": "MSFT"
}

st.markdown("<h2 style='text-align: center;'>📊 AI 실시간 애널리스트 리포트</h2>", unsafe_allow_html=True)

# ==========================================
# 🔍 1. 검색창 & 새로고침 버튼 & 띄어쓰기 무시 로직
# ==========================================
col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명/티커 검색", "TIGER 반도체TOP10")
with col_btn:
    st.write("")
    st.write("")
    st.button("🔄 갱신")

# 공백 제거 및 대문자 변환으로 찰떡같이 검색어 매칭
clean_query = search_query.replace(" ", "").upper()
clean_map = {key.replace(" ", "").upper(): value for key, value in SYMBOL_MAP.items()}
symbol = clean_map.get(clean_query, search_query) # 목록에 없으면 입력값 그대로 검색 (예: TSLA)

# ==========================================
# 📈 2. 데이터 다운로드 및 보조지표 계산
# ==========================================
with st.spinner(f"'{search_query}' 실시간 데이터 분석 중... 🚀"):
    df = yf.download(symbol, period="1y", progress=False)

if df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다. 종목명을 다시 확인해주세요.")
else:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    # 지표 계산
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    
    # RSI 계산
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # MACD 계산
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    # 볼린저 밴드 계산
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

    # 상태 텍스트
    ma_txt = "상승 추세" if curr_price > last['MA20'] > last['MA50'] else ("단기 하락 추세" if curr_price < last['MA20'] else "방향성 탐색")
    rsi_txt = "과매도 구간" if float(last['RSI']) < 40 else ("과매수 구간" if float(last['RSI']) > 70 else "중립 구간")
    macd_txt = "강세 신호" if last['MACD'] > last['Signal'] else "약세 신호"
    vol_txt = "거래량 증가" if curr_vol > avg_vol * 1.2 else "거래량 감소/평이"
    bb_txt = "하단 근접" if curr_price < last['BB_Lower'] * 1.05 else ("상단 근접" if curr_price > last['BB_Upper'] * 0.95 else "밴드 내 횡보")

    # ==========================================
    # 🖥️ 3. 화면 UI 렌더링 시작
    # ==========================================
    
    # [1] 상단 핵심 가격
    c1, c2 = st.columns(2)
    c1.metric("정규장 종가", f"{c}{curr_price:,.0f}", f"{change_val:+,.0f} ({change_pct:+.2f}%)")
    c2.metric("52주 고점 / 저점", f"{c}{high_52:,.0f} / {c}{low_52:,.0f}", f"고점 대비 {((curr_price-high_52)/high_52)*100:.1f}%", delta_color="inverse")
    st.markdown("---")

    # [2] 2x2 추세 및 모멘텀 그리드
    st.subheader("📊 추세 및 모멘텀 분석")
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**📉 이동평균선 (20/50일)**\n\n### {ma_txt}\n\n20일선: {c}{float(last['MA20']):,.0f}\n\n50일선: {c}{float(last['MA50']):,.0f}")
        st.success(f"**📈 RSI (14)**\n\n### 약 {float(last['RSI']):.0f} - {rsi_txt}\n\n현재 매수/매도 강도를 나타냅니다.")
    with col2:
        st.warning(f"**📊 거래량 패턴**\n\n### {vol_txt}\n\n최근 20일 평균 대비 거래량 수준입니다.")
        st.error(f"**🎯 MACD / 볼린저밴드**\n\n### {macd_txt} / {bb_txt}\n\nMACD: {float(last['MACD']):.2f}\n\n밴드 하단: {c}{float(last['BB_Lower']):,.0f}")
    st.markdown("---")

    # [3] 5단계 주요 지지 / 저항 레벨
    st.subheader("🎯 주요 지지 / 저항 레벨")
    pivot = (float(last['High']) + float(last['Low']) + curr_price) / 3
    res1 = (2 * pivot) - float(last['Low'])
    res2 = pivot + (float(last['High']) - float(last['Low']))
    sup1 = (2 * pivot) - float(last['High'])
    sup2 = pivot - (float(last['High']) - float(last['Low']))

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.error(f"지지 2\n\n**{c}{sup2:,.0f}**")
    s2.error(f"지지 1\n\n**{c}{sup1:,.0f}**")
    s3.info(f"피벗\n\n**{c}{pivot:,.0f}**") # 아까 에러났던 부분 파란색(info)으로 수정 완료!
    s4.success(f"저항 1\n\n**{c}{res1:,.0f}**")
    s5.success(f"저항 2\n\n**{c}{res2:,.0f}**")
    st.markdown("---")

    # [4] AI 분석 프롬프트 및 출력
    st.subheader("🤖 AI 투자 전망 및 시나리오 분석")
    prompt = f"""
    너는 최고 수준의 월가 애널리스트야. '{search_query}' 종목의 실시간 데이터를 바탕으로 간결하게 브리핑해.
    
    [데이터] 현재가: {curr_price} / 20일선: {float(last['MA20'])} / RSI: {float(last['RSI'])} / MACD: {macd_txt} / BB: {bb_txt} / 1차지지: {sup1} / 1차저항: {res1}
    
    [양식] (반드시 마크다운으로 작성)
    ### 📌 단기/중기 전망
    * **단기 (1~2주):** (1줄 요약)
    * **중기 (1~3개월):** (1줄 요약)
    
    ### 🟢 강세 시나리오
    (상승 돌파 시 긍정적 트리거 2줄 이내)
    
    ### 🔴 약세 시나리오
    (지지선 이탈 시 부정적 리스크 2줄 이내)
    """

    try:
        with st.spinner("AI가 데이터를 종합하여 시나리오를 작성 중입니다... ✍️"):
            response = model.generate_content(prompt)
            st.markdown(response.text)
    except Exception as e:
        st.error("AI 시나리오를 불러오는 데 실패했습니다.")

    st.caption(f"분석 기준일: {datetime.now().strftime('%Y.%m.%d')} | 데이터: Yahoo Finance")
