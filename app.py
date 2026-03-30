import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# 📱 폰에서 보기 좋은 모바일 화면(다크모드 느낌) 설정
st.set_page_config(page_title="실시간 주식 대시보드", page_icon="📈", layout="centered")

# --- 종목 코드 매핑 ---
SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS",
    "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS",
    "SK하이닉스": "000660.KS",
    "NVDA": "NVDA",
    "ALAB": "ALAB"
}

# --- 상단 검색창 ---
st.title("📊 실시간 기술적 분석")
search_query = st.text_input("종목명 검색 (예: 삼성전자, NVDA)", "TIGER 반도체TOP10")
symbol = SYMBOL_MAP.get(search_query, search_query)

# --- 데이터 가져오기 ---
with st.spinner(f"'{search_query}' 데이터를 긁어오는 중... 🚀"):
    df = yf.download(symbol, period="1y", progress=False)

if df.empty:
    st.error("❌ 데이터를 불러오지 못했습니다. 종목명을 다시 확인해주세요.")
else:
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.droplevel(1)

    # 지표 계산
    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    curr_price = float(last['Close'])
    prev_price = float(prev['Close'])
    change_val = curr_price - prev_price
    change_pct = (change_val / prev_price) * 100
    
    high_52 = float(df['High'].max())
    low_52 = float(df['Low'].min())
    
    c = "₩" if ".KS" in symbol or ".KQ" in symbol else "$"

    # --- 1. 핵심 가격 정보 (예쁜 지표 카드) ---
    col1, col2, col3 = st.columns(3)
    col1.metric("정규장 종가", f"{c}{curr_price:,.0f}", f"{change_val:+,.0f} ({change_pct:+.2f}%)")
    col2.metric("52주 고점", f"{c}{high_52:,.0f}", f"고점대비 {((curr_price-high_52)/high_52)*100:.1f}%", delta_color="inverse")
    col3.metric("최근 거래량", f"{float(last['Volume'])/10000:,.0f}만주")

    st.divider()

    # --- 2. 분석 결과 카드 ---
    st.subheader("🔍 추세 및 모멘텀 분석")
    
    # 상태 판단
    ma_status = "🟢 상승 전환 시도 (20일선 돌파)" if curr_price > last['MA20'] else "🔴 단기 하락 추세"
    
    col_a, col_b = st.columns(2)
    with col_a:
        st.info(f"**이동평균 (20/50일)**\n\n{ma_status}\n\n현재가: {c}{curr_price:,.0f}\n\n20일선: {c}{float(last['MA20']):,.0f}")
    with col_b:
        st.warning(f"**RSI / 거래량**\n\n방향성 탐색 구간\n\n전일 대비 가격 변동이 발생하며 매물 소화 중입니다.")

    st.divider()

    # --- 3. 지지/저항 레벨 ---
    st.subheader("🎯 주요 지지 / 저항 레벨")
    pivot = (float(last['High']) + float(last['Low']) + curr_price) / 3
    res1 = (2 * pivot) - float(last['Low'])
    sup1 = (2 * pivot) - float(last['High'])
    
    # 스트림릿 컬럼으로 박스 느낌 내기
    sc1, sc2, sc3 = st.columns(3)
    sc1.success(f"🔼 1차 저항\n\n**{c}{res1:,.0f}**")
    sc2.info(f"⏺️ 피벗(기준)\n\n**{c}{pivot:,.0f}**")
    sc3.error(f"🔽 1차 지지\n\n**{c}{sup1:,.0f}**")

    st.divider()
    
    st.caption(f"분석 기준일: {datetime.now().strftime('%Y.%m.%d')} | 데이터 출처: Yahoo Finance")
