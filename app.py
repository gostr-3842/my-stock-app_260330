import streamlit as st
import pandas as pd
from utils import format_price, load_tickers
from data_manager import load_stock_data, get_investor_data, analyze_investor_flow
from ai_engine import get_ai_scenarios

st.set_page_config(page_title="AI 실시간 주식 리포트", page_icon="📈", layout="centered")
# ... (기존 스타일 코드 생략, 이전 파일과 동일)

df_tickers = load_tickers()
query = st.text_input("종목 검색", "", placeholder="예: 삼성전자, NVDA", label_visibility="collapsed")
st.button("🔄 갱신")

if query:
    clean_query = query.replace(" ", "").upper()
    mask = df_tickers["name"].str.contains(clean_query, na=False)
    results = df_tickers[mask]
    if not results.empty:
        selected_name = st.selectbox("선택", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name
    else: symbol = query.upper(); search_query = query.upper()
else: symbol = "005930.KS"; search_query = "삼성전자"

with st.spinner("분석 중..."):
    df = load_stock_data(symbol)
    if df is not None:
        # 1. 수급 데이터 가져오기 & 미러링 로직
        investor_df = get_investor_data(symbol)
        is_mirrored = False
        if investor_df is None or investor_df.iloc[0]['frgn_ntby_qty'] == 0:
            # 수급 데이터 없으면 삼성전자(005930)로 미러링
            investor_df = get_investor_data("005930.KS")
            is_mirrored = True
        
        supply_text = analyze_investor_flow(investor_df, is_mirrored, "삼성전자")
        
        # 2. 기존 지표 계산 및 UI 렌더링 (기존 코드와 동일하게 쭉 진행)
        last = df.iloc[-1]; curr_price = float(last['Close'])
        rsi_val = last['RSI'] if not pd.isna(last['RSI']) else 50
        ai_data = get_ai_scenarios(search_query, curr_price, rsi_val, supply_text)
        
        # ... (중략: 기존 현재가, 지표분석, 피벗박스 UI 코드들) ...

        # 3. [추가] 맨 하단 외국인 수급 정보 표시
        st.markdown("<div class='section-title'>외국인 수급 동향 (최근 3일)</div>", unsafe_allow_html=True)
        inv_rows = ""
        
        # 👇 방어 로직 추가: investor_df가 비어있지 않을 때만 반복문 실행
        if investor_df is not None and not investor_df.empty:
            for _, row in investor_df.iterrows():
                date_str = str(row['stck_bsop_date'])[4:6] + "/" + str(row['stck_bsop_date'])[6:8]
                qty = row['frgn_ntby_qty']
                color = "txt-green" if qty > 0 else "txt-red"
                inv_rows += f"<div style='display:flex; justify-content:space-between; margin-bottom:5px;'><span>{date_str}</span><span class='{color}'>{qty:+,d} 주</span></div>"
        else:
            inv_rows = "<div style='color:#ef4444; font-size:0.9rem;'>수급 API 연동 지연 또는 키 설정 오류입니다.</div>"
            date_str = str(row['stck_bsop_date'])[4:6] + "/" + str(row['stck_bsop_date'])[6:8]
            qty = row['frgn_ntby_qty']
            color = "txt-green" if qty > 0 else "txt-red"
            inv_rows += f"<div style='display:flex; justify-content:space-between; margin-bottom:5px;'><span>{date_str}</span><span class='{color}'>{qty:+,d} 주</span></div>"
            
        st.markdown(f"""
        <div class="vip-card">
            {inv_rows}
            <div style="height:1px; background:#1f2937; margin:10px 0;"></div>
            <div class="ai-text" style="font-size:0.85rem; color:#9ca3af;">{supply_text}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.error("데이터 로드 실패")
