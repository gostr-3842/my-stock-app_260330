import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

from utils import format_price, load_tickers
from data_manager import load_stock_data, get_investor_data, analyze_investor_flow, get_market_status
from ai_engine import get_ai_scenarios

# 📱 1. VIP 스타일 UI 설정
st.set_page_config(page_title="GoStraight AI 터미널", page_icon="📉", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #d1d5db; font-family: 'Pretendard', sans-serif; }
    .market-bar { display: flex; justify-content: space-between; background: #171c26; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #1f2937; }
    .market-item { text-align: center; flex: 1; }
    .m-label { font-size: 0.75rem; color: #6b7280; margin-bottom: 5px; }
    .m-value { font-size: 1rem; font-weight: bold; }
    .section-title { font-size: 1.1rem; font-weight: bold; color: #9ca3af; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; }
    .vip-card { background-color: #171c26; border-radius: 12px; padding: 18px; position: relative; border: 1px solid #1f2937; }
    .txt-green { color: #10b981 !important; }
    .txt-red { color: #ef4444 !important; }
    .txt-yellow { color: #f59e0b !important; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #10b981; color: #000; }
    .badge-sell { background-color: #ef4444; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🏁 [NEW] 상단 시장 관제 바
m_data = get_market_status()
st.markdown(f"""
<div class="market-bar">
    <div class="market-item">
        <div class="m-label">KOSPI 외인</div>
        <div class="m-value {"txt-green" if m_data['KOSPI'] > 0 else "txt-red"}">{m_data['KOSPI']:+,d}억</div>
    </div>
    <div class="market-item" style="border-left: 1px solid #1f2937; border-right: 1px solid #1f2937;">
        <div class="m-label">KOSDAQ 외인</div>
        <div class="m-value {"txt-green" if m_data['KOSDAQ'] > 0 else "txt-red"}">{m_data['KOSDAQ']:+,d}억</div>
    </div>
    <div class="market-item">
        <div class="m-label">🔥 외인 선물</div>
        <div class="m-value {"txt-green" if m_data['FUTURES'] > 0 else "txt-red"}" style="font-size:1.1rem;">{m_data['FUTURES']:+,d}억</div>
    </div>
</div>
""", unsafe_allow_html=True)

# 🔍 2. 종목 검색부
df_tickers = load_tickers()
macro_options = ["특이사항 없음", "전쟁 및 환율 급등(보수적)", "금리 인하 기대(긍정적)", "경기 침체 우려(방어적)"]
macro_selected = st.selectbox("🌍 매크로 설정", macro_options)

query = st.text_input("🔍 종목 검색", "", placeholder="예: 삼성전자")
symbol, search_query = "", ""

if query:
    mask = df_tickers["name"].str.contains(query, na=False)
    results = df_tickers[mask]
    if not results.empty:
        selected_name = st.selectbox("결과 선택", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name

if st.button("분석 시작", use_container_width=True):
    st.session_state['analyze_mode'] = True
    st.session_state['symbol'] = symbol
    st.session_state['search_query'] = search_query

info_placeholder = st.empty()

# 📊 3. 대시보드 출력
if st.session_state.get('analyze_mode', False):
    with st.spinner("5분 주기 최신 데이터 로드 중..."):
        df, fetch_time = load_stock_data(st.session_state['symbol'])
        if df is not None:
            info_placeholder.markdown(f"<div style='text-align: center; color: #6b7280; font-size: 0.8rem;'>⏱️ 5분 단위 자동 갱신 중 (업데이트: {fetch_time})</div>", unsafe_allow_html=True)
            
            # 수급 로직 (잠정치 포함)
            investor_df = get_investor_data(st.session_state['symbol'])
            supply_text = analyze_investor_flow(investor_df, False, "")
            
            # AI 분석 및 UI 렌더링 (기존 로직 유지)
            # ... (이전 코드의 카드 및 지표 레이아웃 동일)
            # 수급 동향 출력 시 '집계 중' 로직 포함
            inv_rows = ""
            today_str = datetime.now(timezone(timedelta(hours=9))).strftime("%m/%d")
            for _, row in investor_df.head(3).iterrows():
                d_str = f"{str(row['stck_bsop_date'])[4:6]}/{str(row['stck_bsop_date'])[6:8]}"
                qty = int(row.get('frgn_ntby_qty', 0)) if pd.notna(row.get('frgn_ntby_qty')) else 0
                val_text = f"{qty:+,d} 주" if (d_str != today_str or qty != 0) else "집계 중(잠정)"
                cls = "txt-green" if qty > 0 else "txt-red" if qty < 0 else "txt-yellow"
                inv_rows += f"<div style='display:flex; justify-content:space-between;'><span>{d_str}</span><span class='{cls}'>{val_text}</span></div>"
            
            st.markdown(f'<div class="vip-card">{inv_rows}</div>', unsafe_allow_html=True)
