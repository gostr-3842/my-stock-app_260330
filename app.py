import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai

# 📱 기본 설정
st.set_page_config(page_title="AI 실시간 주식 대시보드", page_icon="📈", layout="centered")

# 🧠 Gemini API 설정 (스트림릿 금고에서 키 꺼내오기)
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-2.5-flash') # 빠르고 똑똑한 최신 모델
except:
    st.error("⚠️ API 키가 설정되지 않았습니다. 앱 설정의 Secrets를 확인해주세요.")

SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS",
    "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "NVDA": "NVDA",
}

st.title("📊 AI 기술적 분석 리포트")
search_query = st.text_input("종목명 검색 (예: 삼성전자, NVDA)", "TIGER 반도체TOP10")
symbol = SYMBOL_MAP.get(search_query, search_query)

# --- 데이터 긁어오기 ---
with st.spinner(f"'{search_query}' 실시간 데이터 분석 중... 🚀"):
    df = yf.download(symbol, period="1y", progress=False)

if df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다. 종목명을 확인해주세요.")
else:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    curr_price = float(last['Close'])
    prev_price = float(prev['Close'])
    change_val = curr_price - prev_price
    change_pct = (change_val / prev_price) * 100
    high_52 = float(df['High'].max())
    
    c = "₩" if ".KS" in symbol or ".KQ" in symbol else "$"

    # --- 1. 가격 정보 UI ---
    col1, col2, col3 = st.columns(3)
    col1.metric("정규장 종가", f"{c}{curr_price:,.0f}", f"{change_val:+,.0f} ({change_pct:+.2f}%)")
    col2.metric("52주 고점", f"{c}{high_52:,.0f}", f"고점대비 {((curr_price-high_52)/high_52)*100:.1f}%", delta_color="inverse")
    col3.metric("이동평균(20일)", f"{c}{float(last['MA20']):,.0f}")
    st.divider()

    # --- 2. AI 애널리스트 분석 요청 ---
    st.subheader("🤖 제미나이(AI) 투자 시나리오 및 판정")
    
    # AI에게 숫자를 던져주고 글을 써달라고 명령(프롬프트)
    prompt = f"""
    너는 냉철하고 전문적인 주식 애널리스트야. 다음 실시간 데이터를 바탕으로 '{search_query}' 종목의 분석 리포트를 아주 간결하게 마크다운으로 작성해줘.
    
    [실시간 데이터]
    - 현재가: {curr_price:,.0f}
    - 전일 대비 변동률: {change_pct:+.2f}%
    - 20일 이동평균선: {float(last['MA20']):,.0f}
    - 52주 고점: {high_52:,.0f}
    
    [작성 양식] (반드시 아래 3가지 항목만 핵심만 짧게 적어줄 것)
    1. 🚦 **최종 판정**: (매수 / 매도 / 보류 중 택 1, 이유 1줄)
    2. 📈 **강세 시나리오**: (상승 시 2줄 이내로 전망)
    3. 📉 **약세 시나리오**: (하락 시 2줄 이내로 전망)
    """

    try:
        # AI가 생각하고 답변을 적는 시간
        with st.spinner("AI가 데이터를 바탕으로 시나리오를 작성하고 있습니다... ✍️"):
            response = model.generate_content(prompt)
            # AI가 써준 글을 화면에 예쁘게 출력
            st.info(response.text)
    except Exception as e:
        st.error("AI 분석 중 에러가 발생했습니다. 잠시 후 다시 시도해주세요.")

    st.divider()

    # --- 3. 지지/저항 레벨 UI ---
    st.subheader("🎯 주요 지지 / 저항 레벨")
    pivot = (float(last['High']) + float(last['Low']) + curr_price) / 3
    res1 = (2 * pivot) - float(last['Low'])
    sup1 = (2 * pivot) - float(last['High'])
    
    sc1, sc2, sc3 = st.columns(3)
    sc1.success(f"🔼 1차 저항\n\n**{c}{res1:,.0f}**")
    sc2.info(f"⏺️ 피벗(기준)\n\n**{c}{pivot:,.0f}**")
    sc3.error(f"🔽 1차 지지\n\n**{c}{sup1:,.0f}**")

    st.caption(f"분석 기준일: {datetime.now().strftime('%Y.%m.%d')} | 데이터: Yahoo Finance | AI: Gemini 2.5 Flash")
