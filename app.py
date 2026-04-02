import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

from utils import format_price, load_tickers
from data_manager import load_stock_data, get_investor_data, analyze_investor_flow, get_market_status, safe_int
from ai_engine import get_ai_scenarios

# 📱 1. VIP 스타일 UI 설정
st.set_page_config(page_title="GoStraight AI 터미널", page_icon="📉", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #d1d5db; font-family: 'Pretendard', sans-serif; }
    .market-bar { display: flex; justify-content: space-between; background: #171c26; padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 1px solid #1f2937; }
    .market-item { text-align: center; flex: 1; }
    .m-label { font-size: 0.75rem; color: #6b7280; margin-bottom: 5px; }
    .m-value { font-size: 1.1rem; font-weight: bold; }
    .section-title { font-size: 1.1rem; font-weight: bold; color: #9ca3af; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; }
    .vip-card { background-color: #171c26; border-radius: 12px; padding: 18px; position: relative; border: 1px solid #1f2937; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .card-title { font-size: 0.85rem; color: #6b7280; margin-bottom: 8px; font-weight: 600; }
    .card-value { font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 8px; line-height: 1.3; }
    .card-desc { font-size: 0.85rem; color: #9ca3af; line-height: 1.5; }
    .top-price-val { font-size: 1.8rem; font-weight: 800; color: #ffffff; line-height: 1.1; }
    .txt-green { color: #10b981 !important; }
    .txt-red { color: #ef4444 !important; }
    .txt-yellow { color: #f59e0b !important; }
    .dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; position: absolute; top: 18px; right: 18px; }
    .dot-green { background-color: #10b981; box-shadow: 0 0 5px #10b981; }
    .dot-red { background-color: #ef4444; box-shadow: 0 0 5px #ef4444; }
    .dot-yellow { background-color: #f59e0b; box-shadow: 0 0 5px #f59e0b; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; margin-bottom: 15px; }
    .pivot-box { border-radius: 8px; padding: 12px 0; text-align: center; display: flex; flex-direction: column; border: 1px solid #2d3748;}
    .pv-title { font-size: 0.75rem; margin-bottom: 4px; opacity: 0.8;}
    .pv-val { font-size: 1.1rem; font-weight: 700; }
    .bg-sup { background-color: rgba(59, 130, 246, 0.15); border-color: rgba(59, 130, 246, 0.4); color: #93c5fd; }
    .bg-piv { background-color: rgba(139, 92, 246, 0.15); border-color: rgba(139, 92, 246, 0.4); color: #c4b5fd; }
    .bg-res { background-color: rgba(239, 68, 68, 0.15); border-color: rgba(239, 68, 68, 0.4); color: #fca5a5; }
    .bg-ath { background-color: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.4); color: #fcd34d; }
    .ai-row { display: flex; gap: 12px; margin-bottom: 10px; }
    .ai-label { min-width: 80px; font-size: 0.85rem; color: #9ca3af; }
    .ai-text { font-size: 0.9rem; color: #e5e7eb; line-height: 1.6; }
    .scenario-box { border-radius: 8px; padding: 15px; flex: 1; border: 1px solid; }
    .box-bull { background-color: rgba(16, 185, 129, 0.05); border-color: rgba(16, 185, 129, 0.3); }
    .box-bear { background-color: rgba(239, 68, 68, 0.05); border-color: rgba(239, 68, 68, 0.3); }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #10b981; color: #000; }
    .badge-sell { background-color: #ef4444; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🏁 상단 시장 관제 바
m_data = get_market_status()

if m_data.get("ERROR"):
    st.error("🚨 Streamlit Cloud 설정(Settings -> Secrets)에서 KIS_APP_KEY와 KIS_APP_SECRET을 등록해주세요.")
else:
    st.markdown(f"""
    <div class="market-bar">
        <div class="market-item">
            <div class="m-label">KOSPI 외인</div>
            <div class="m-value {"txt-green" if m_data.get('KOSPI',0) > 0 else "txt-red"}">{m_data.get('KOSPI',0):+,d}억</div>
        </div>
        <div class="market-item" style="border-left: 1px solid #1f2937; border-right: 1px solid #1f2937;">
            <div class="m-label">KOSDAQ 외인</div>
            <div class="m-value {"txt-green" if m_data.get('KOSDAQ',0) > 0 else "txt-red"}">{m_data.get('KOSDAQ',0):+,d}억</div>
        </div>
        <div class="market-item">
            <div class="m-label">🔥 외인 선물</div>
            <div class="m-value {"txt-green" if m_data.get('FUTURES',0) > 0 else "txt-red"}" style="font-size:1.1rem;">{m_data.get('FUTURES',0):+,d}억</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# 🔍 2. 종목 검색부
df_tickers = load_tickers()
macro_options = ["특이사항 없음", "전쟁 장기화 및 환율 급등 (극도로 보수적)", "글로벌 금리 인하 기대감 (긍정적 시각)", "경기 침체 우려 (방어적 접근)", "인플레이션 고착화 (기술주 부담)"]
macro_selected = st.selectbox("🌍 매크로 설정", macro_options)
macro_keyword = "" if "특이사항 없음" in macro_selected else macro_selected

query = st.text_input("🔍 종목 검색", "", placeholder="예: 삼성전자, 하이닉스")
symbol = ""
search_query = ""

if query:
    clean_query = query.replace(" ", "").upper()
    mask = df_tickers["name"].astype(str).str.replace(" ", "").str.upper().str.contains(clean_query, na=False)
    results = df_tickers[mask]

    if not results.empty:
        selected_name = st.selectbox("결과 선택", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name
    else:
        symbol = query.upper()
        search_query = query.upper()

if st.button("분석 시작", use_container_width=True):
    if query: 
        st.session_state['analyze_mode'] = True
        st.session_state['symbol'] = symbol
        st.session_state['search_query'] = search_query
        st.session_state['macro_keyword'] = macro_keyword
    else:
        st.warning("종목을 먼저 입력해 주세요!")
        st.session_state['analyze_mode'] = False

info_placeholder = st.empty()

# 📊 3. 대시보드 렌더링부
if st.session_state.get('analyze_mode', False):
    current_symbol = st.session_state['symbol']
    current_search_query = st.session_state['search_query']
    current_macro = st.session_state.get('macro_keyword', "")

    with st.spinner("5분 주기 최신 데이터 로드 중..."):
        df, fetch_time = load_stock_data(current_symbol)
        
        if df is not None:
            info_placeholder.markdown(f"<div style='text-align: center; color: #9ca3af; font-size: 0.85rem; margin-top: -10px; margin-bottom: 20px;'>⏱️ 데이터는 5분 단위로 갱신됩니다. <span style='opacity:0.7;'>(마지막 업데이트: {fetch_time})</span></div>", unsafe_allow_html=True)
            
            investor_df = get_investor_data(current_symbol)
            is_mirrored = False
            
            # [핵심 수술 부위] 에러를 뿜던 127번 라인을 안전하게 분해
            first_row_val = 0
            if investor_df is not None and not investor_df.empty:
                first_row_val = safe_int(investor_df.iloc[0].get('frgn_ntby_qty', 0))
            
            # 수급 데이터가 없거나 0으로 채워진 상태라면 삼성전자 데이터로 미러링 시도
            if investor_df is None or (not investor_df.empty and first_row_val == 0):
                investor_df = get_investor_data("005930.KS")
                is_mirrored = True
            
            supply_text = analyze_investor_flow(investor_df, is_mirrored, "삼성전자")
            last = df.iloc[-1]
            curr_price = float(last['Close'])
            high_52 = float(df['High'].max())
            rsi_val = last['RSI'] if not pd.isna(last['RSI']) else 50
            
            ai_data = get_ai_scenarios(current_search_query, curr_price, rsi_val, supply_text, current_macro)
            decision = ai_data.get('decision', '관망')
            badge_cls = "badge-buy" if decision == "매수" else ("badge-sell" if decision == "매도" else "badge-hold")

            st.markdown(f'<span class="badge {badge_cls}">{decision}</span><h2 style="margin:0;">{current_search_query} <br><span style="font-size:1rem;color:#6b7280;font-weight:normal;">{current_symbol}</span></h2>', unsafe_allow_html=True)
            
            change_pct = ((curr_price - float(df.iloc[-2]['Close'])) / float(df.iloc[-2]['Close'])) * 100
            
            st.markdown(f"""
            <div class="grid-2" style="margin-top:25px;">
                <div class="vip-card">
                    <div class="card-title">현재가</div>
                    <div class="top-price-val">{format_price(curr_price, current_symbol)}</div>
                    <div class="{"txt-red" if change_pct < 0 else "txt-green"}">{change_pct:+.2f}%</div>
                </div>
                <div class="vip-card">
                    <div class="card-title">52주 고점 대비</div>
                    <div class="top-price-val" style="font-size:1.4rem;">{format_price(high_52, current_symbol)}</div>
                    <div class="txt-red">{((curr_price-high_52)/high_52)*100:.1f}% 하락</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='section-title'>추세 및 지표 분석</div>", unsafe_allow_html=True)
            ma_status = "상승 추세" if curr_price > last['MA20'] else "하락 추세"
            
            st.markdown(f"""
            <div class="grid-2">
                <div class="vip-card">
                    <span class="dot {"dot-green" if "상승" in ma_status else "dot-red"}"></span>
                    <div class="card-title">이동평균 (20일)</div>
                    <div class="card-value">{ma_status}</div>
                    <div class="card-desc">현재가가 20일선 {"위" if "상승" in ma_status else "아래"}에 머물고 있습니다.</div>
                </div>
                <div class="vip-card">
                    <span class="dot {"dot-green" if rsi_val < 30 else ("dot-red" if rsi_val > 70 else "dot-yellow")}"></span>
                    <div class="card-title">RSI (14)</div>
                    <div class="card-value">RSI {rsi_val:.0f}</div>
                    <div class="card-desc">{"과매도" if rsi_val < 30 else ("과매수" if rsi_val > 70 else "중립")} 구간에 진입해 있습니다.</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='section-title'>주요 지지 / 저항 레벨</div>", unsafe_allow_html=True)
            piv = (float(last['High']) + float(last['Low']) + curr_price) / 3
            s1 = 2 * piv - float(last['High'])
            s2 = piv - (float(last['High']) - float(last['Low']))
            r1 = 2 * piv - float(last['Low'])
            r2 = piv + (float(last['High']) - float(last['Low']))
            
            st.markdown(f"""
            <div class="grid-3">
                <div class="pivot-box bg-sup"><div class="pv-title">지지 2</div><div class="pv-val">{format_price(s2, current_symbol)}</div></div>
                <div class="pivot-box bg-sup"><div class="pv-title">지지 1</div><div class="pv-val">{format_price(s1, current_symbol)}</div></div>
                <div class="pivot-box bg-piv"><div class="pv-title">피벗 (중심)</div><div class="pv-val">{format_price(piv, current_symbol)}</div></div>
            </div>
            <div class="grid-3">
                <div class="pivot-box bg-res"><div class="pv-title">저항 1</div><div class="pv-val">{format_price(r1, current_symbol)}</div></div>
                <div class="pivot-box bg-res"><div class="pv-title">저항 2</div><div class="pv-val">{format_price(r2, current_symbol)}</div></div>
                <div class="pivot-box bg-ath"><div class="pv-title">52주 고점</div><div class="pv-val">{format_price(high_52, current_symbol)}</div></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='section-title'>AI 투자 전략 리포트</div>", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="vip-card">
                <div class="ai-row"><div class="ai-label">단기 전망</div><div class="ai-text">{ai_data.get('short_term')}</div></div>
                <div style="height:1px; background:#1f2937; margin:10px 0;"></div>
                <div class="ai-row"><div class="ai-label">중기 전망</div><div class="ai-text">{ai_data.get('mid_term')}</div></div>
            </div>
            <div class="grid-2" style="margin-top:10px;">
                <div class="scenario-box box-bull"><div class="txt-green" style="font-weight:bold; margin-bottom:5px;">🟢 강세 근거</div><div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bull')}</div></div>
                <div class="scenario-box box-bear"><div class="txt-red" style="font-weight:bold; margin-bottom:5px;">🔴 약세 근거</div><div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bear')}</div></div>
            </div>
            """, unsafe_allow_html=True)

            st.markdown("<div class='section-title'>외국인 수급 동향 (최근 3일)</div>", unsafe_allow_html=True)
            inv_rows = ""
            if investor_df is not None and not investor_df.empty:
                today_str = datetime.now(timezone(timedelta(hours=9))).strftime("%m/%d")
                for _, row in investor_df.head(3).iterrows():
                    date_val = str(row['stck_bsop_date'])
                    d_str = f"{date_val[4:6]}/{date_val[6:8]}"
                    
                    # [방어막 적용] 어떤 값이 오든 안전하게 정수(또는 0)로 변환
                    qty = safe_int(row.get('frgn_ntby_qty', 0))
                    
                    if d_str == today_str and qty == 0:
                        display_qty = "집계 중(잠정)"
                        color = "txt-yellow"
                    else:
                        display_qty = f"{qty:+,d} 주"
                        color = "txt-green" if qty > 0 else "txt-red" if qty < 0 else "txt-yellow"
                    
                    inv_rows += f"<div style='display:flex; justify-content:space-between; margin-bottom:5px;'><span>{d_str}</span><span class='{color}'>{display_qty}</span></div>"
            else:
                inv_rows = "<div style='color:#9ca3af; font-size:0.85rem;'>현재 수급 데이터를 불러올 수 없습니다.</div>"

            st.markdown(f"""
            <div class="vip-card">
                {inv_rows}
                <div style="height:1px; background:#1f2937; margin:10px 0;"></div>
                <div class="ai-text" style="font-size:0.85rem; color:#9ca3af;">{supply_text}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error("데이터 로드 실패")
            info_placeholder.markdown("<div style='text-align: center; color: #9ca3af; font-size: 0.85rem; margin-top: -10px; margin-bottom: 20px;'>⏱️ 데이터는 5분 단위로 갱신됩니다.</div>", unsafe_allow_html=True)
else:
    info_placeholder.markdown("<div style='text-align: center; color: #9ca3af; font-size: 0.85rem; margin-top: -10px; margin-bottom: 20px;'>⏱️ 데이터는 5분 단위로 갱신됩니다.</div>", unsafe_allow_html=True)
    st.info("💡 위에서 매크로 환경과 종목을 설정한 뒤 '분석 시작' 버튼을 눌러주세요.")
