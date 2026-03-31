import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from google import genai
from groq import Groq
import json
import re
import time

# 📱 1. VIP 스타일 UI 설정
st.set_page_config(page_title="AI 실시간 주식 리포트", page_icon="📈", layout="centered")

st.markdown("""
<style>
    .stApp { background-color: #0b0e14; color: #d1d5db; font-family: 'Pretendard', sans-serif; }
    .section-title { font-size: 1.1rem; font-weight: bold; color: #9ca3af; margin-top: 30px; margin-bottom: 15px; border-bottom: 1px solid #1f2937; padding-bottom: 5px; }
    .vip-card { background-color: #171c26; border-radius: 12px; padding: 18px; position: relative; border: 1px solid #1f2937; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .card-title { font-size: 0.85rem; color: #6b7280; margin-bottom: 8px; font-weight: 600; }
    .card-value { font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 8px; line-height: 1.3; }
    .card-desc { font-size: 0.85rem; color: #9ca3af; line-height: 1.5; }
    .top-price-title { font-size: 0.85rem; color: #6b7280; margin-bottom: 4px; }
    .top-price-val { font-size: 1.8rem; font-weight: 800; color: #ffffff; line-height: 1.1; }
    .txt-green { color: #10b981 !important; }
    .txt-red { color: #ef4444 !important; }
    .txt-yellow { color: #f59e0b !important; }
    .dot { height: 8px; width: 8px; border-radius: 50%; display: inline-block; position: absolute; top: 18px; right: 18px; }
    .dot-green { background-color: #10b981; box-shadow: 0 0 5px #10b981; }
    .dot-red { background-color: #ef4444; box-shadow: 0 0 5px #ef4444; }
    .dot-yellow { background-color: #f59e0b; box-shadow: 0 0 5px #f59e0b; }
    .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
    .pivot-box { border-radius: 8px; padding: 12px 0; text-align: center; display: flex; flex-direction: column; border: 1px solid #2d3748;}
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

# 🛠️ 이게 아까 날아갔던 함수입니다!
def format_price(val, sym):
    if ".KS" in sym or ".KQ" in sym: return f"₩{val:,.0f}"
    return f"${val:,.2f}"

# 🔍 2. 스마트 검색창 (CSV 기반 자동완성)
@st.cache_data
def load_tickers():
    try:
        # 깃허브에 올린 CSV 파일을 읽어옵니다.
        return pd.read_csv("krx_tickers.csv")
    except Exception:
        # 파일이 아직 없으면 빈 사전을 만듭니다.
        return pd.DataFrame(columns=["name", "ticker"])

df_tickers = load_tickers()

col_search, col_btn = st.columns([4, 1])
with col_search:
    query = st.text_input("종목 검색", "", placeholder="예: 삼성전자, 반도체, NVDA", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

# 💡 유저님이 설계한 검색 & 선택 로직
if query:
    clean_query = query.replace(" ", "").upper()
    # CSV에 검색어(띄어쓰기 무시)가 포함된 모든 종목 찾기
    mask = df_tickers["name"].astype(str).str.replace(" ", "").str.upper().str.contains(clean_query, na=False)
    results = df_tickers[mask]

    if not results.empty:
        # 검색 결과가 있으면 셀렉트박스 표시
        selected_name = st.selectbox("👇 검색 결과에서 선택하세요", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name
    else:
        # 결과가 없으면(미국 주식 등) 입력값 그대로 야후에 던짐
        symbol = query.upper()
        search_query = query.upper()
else:
    # 기본값
    symbol = "396500.KS"
    search_query = "TIGER FN반도체TOP10"

# 🛡️ 3. 데이터 로드 및 AI 엔진
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
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close'])
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA50'] = df['Close'].rolling(50).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        return df, info
    return None, {}

@st.cache_data(ttl=600)
def get_ai_scenarios(q, curr, rsi):
    prompt = f"종목:{q},가:{curr},RSI:{rsi:.1f}. JSON: decision(매수/매도/관망), short_term, mid_term, bull, bear. 한국어."
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(messages=[{"role": "user", "content": prompt}], model="llama-3.3-70b-versatile", response_format={"type": "json_object"})
            return json.loads(completion.choices[0].message.content)
        except: pass
    return {"decision":"관망", "short_term":"AI 분석 로딩 중...", "mid_term":"잠시만 기다려주세요.", "bull":"-", "bear":"-"}

# 📊 4. 메인 화면 렌더링
with st.spinner(f"'{search_query}' 분석 중..."):
    df, info = load_stock_data(symbol)
    
    if df is not None and not df.empty:
        last = df.iloc[-1]
        curr_price = float(last['Close'])
        change_pct = ((curr_price - float(df.iloc[-2]['Close'])) / float(df.iloc[-2]['Close'])) * 100
        high_52 = float(df['High'].max())
        
        rsi_val = last['RSI'] if not pd.isna(last['RSI']) else 50
        ai_data = get_ai_scenarios(search_query, curr_price, rsi_val)
        decision = ai_data.get('decision', '관망')
        badge_cls = "badge-buy" if decision == "매수" else ("badge-sell" if decision == "매도" else "badge-hold")

        # 타이틀 & 뱃지
        st.markdown(f'<span class="badge {badge_cls}">{decision}</span><h2 style="margin:0; font-size:1.8rem;">{search_query} <br><span style="font-size:1rem;color:#6b7280;font-weight:normal;">{symbol}</span></h2>', unsafe_allow_html=True)
        
        # 가격 요약
        st.markdown(f"""
        <div class="grid-2" style="margin-top:25px;">
            <div class="vip-card">
                <div class="card-title">현재가</div>
                <div class="top-price-val">{format_price(curr_price, symbol)}</div>
                <div class="{"txt-red" if change_pct < 0 else "txt-green"}">{change_pct:+.2f}%</div>
            </div>
            <div class="vip-card">
                <div class="card-title">52주 고점 대비</div>
                <div class="top-price-val" style="font-size:1.4rem;">{format_price(high_52, symbol)}</div>
                <div class="txt-red">{((curr_price-high_52)/high_52)*100:.1f}% 하락</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 지표
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

        # AI
        st.markdown("<div class='section-title'>AI 투자 전략 및 시나리오</div>", unsafe_allow_html=True)
        st.markdown(f"""
        <div class="vip-card">
            <div class="ai-row"><div class="ai-label">단기 전망</div><div class="ai-text">{ai_data.get('short_term')}</div></div>
            <div style="height:1px; background:#1f2937; margin:12px 0;"></div>
            <div class="ai-row"><div class="ai-label">중기 전망</div><div class="ai-text">{ai_data.get('mid_term')}</div></div>
        </div>
        <div class="grid-2" style="margin-top:12px;">
            <div class="scenario-box box-bull"><div class="txt-green" style="font-weight:bold; margin-bottom:5px;">🟢 강세 근거</div><div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bull')}</div></div>
            <div class="scenario-box box-bear"><div class="txt-red" style="font-weight:bold; margin-bottom:5px;">🔴 약세 근거</div><div class="ai-text" style="font-size:0.85rem;">{ai_data.get('bear')}</div></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.caption("Data: Yahoo Finance & KRX | AI: Hybrid Analytics Engine")
    else:
        st.error(f"❌ '{symbol}' 데이터를 찾을 수 없습니다. (CSV 파일이 GitHub에 올라가 있는지 확인해 주세요!)")
