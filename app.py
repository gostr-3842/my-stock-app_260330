import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai
import json
import re

# 📱 기본 설정
st.set_page_config(page_title="AI 주식 대시보드", page_icon="📊", layout="centered")

# 🎨 UI 스타일 (다크모드 & 모바일 최적화)
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
    .gray-txt { color: #a0aec0; }
    .box-sup { background-color: rgba(0, 210, 106, 0.1); border: 1px solid #00d26a; border-radius: 8px; padding: 10px; text-align: center; }
    .box-res { background-color: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; border-radius: 8px; padding: 10px; text-align: center; }
    .box-piv { background-color: rgba(255, 170, 0, 0.1); border: 1px solid #ffaa00; border-radius: 8px; padding: 10px; text-align: center; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #00d26a; color: #000; }
    .badge-sell { background-color: #ff4b4b; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🔍 검색 로직
SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS", "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "NVDA": "NVDA", "ALAB": "ALAB", "META": "META", "MSFT": "MSFT"
}

col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명/티커", "TIGER 반도체TOP10", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

clean_query = search_query.replace(" ", "").upper()
clean_map = {key.replace(" ", "").upper(): value for key, value in SYMBOL_MAP.items()}
symbol = clean_map.get(clean_query, search_query)

# 🧠 듀얼 AI 분석 엔진 (캐싱 적용)
@st.cache_data(ttl=600)
def get_ai_report(q, curr, ma20, rsi, macd):
    keys = []
    if "GEMINI_API_KEY_1" in st.secrets: keys.append(st.secrets["GEMINI_API_KEY_1"])
    if "GEMINI_API_KEY_2" in st.secrets: keys.append(st.secrets["GEMINI_API_KEY_2"])
    
    prompt = f"종목:{q},가:{curr},20선:{ma20},RSI:{rsi},MACD:{macd}. JSON: decision(매수/매도/관망), short_term, mid_term, bull, bear"

    for k in keys:
        genai.configure(api_key=k)
        for m in ['gemini-2.0-flash', 'gemini-1.5-flash', 'gemini-1.5-pro']:
            try:
                model = genai.GenerativeModel(m)
                res = model.generate_content(prompt)
                jt = re.sub(r'```[a-zA-Z]*\n|```', '', res.text).strip()
                return json.loads(jt[jt.find('{'):jt.rfind('}')+1])
            except: continue
    return None

# 📈 데이터 처리
with st.spinner("분석 중..."):
    df = yf.download(symbol, period="1y", progress=False)
    if not df.empty:
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.droplevel(1)
        df['MA20'] = df['Close'].rolling(20).mean()
        df['MA50'] = df['Close'].rolling(50).mean()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        df['Signal'] = df['MACD'].ewm(span=9).mean()
        df['BB_Mid'] = df['Close'].rolling(20).mean()
        df['BB_Lower'] = df['BB_Mid'] - (df['Close'].rolling(20).std() * 2)
        df['BB_Upper'] = df['BB_Mid'] + (df['Close'].rolling(20).std() * 2)

        last = df.iloc[-1]
        curr_price = float(last['Close'])
        change_pct = ((curr_price - float(df.iloc[-2]['Close'])) / float(df.iloc[-2]['Close'])) * 100
        
        ai_data = get_ai_report(search_query, curr_price, float(last['MA20']), float(last['RSI']), float(last['MACD']))
        if not ai_data:
            ai_data = {"decision":"관망","short_term":"AI 한도 초과","mid_term":"잠시 후 시도","bull":"데이터 부족","bear":"데이터 부족"}

        # --- UI 시작 ---
        badge_cls = "badge-buy" if ai_data['decision'] == "매수" else ("badge-sell" if ai_data['decision'] == "매도" else "badge-hold")
        st.markdown(f'<span class="badge {badge_cls}">{ai_data["decision"]}</span><h2 style="margin:0;">{search_query}</h2>', unsafe_allow_html=True)
        st.markdown(f'<div class="title-sub">{symbol} | {datetime.now().strftime("%Y.%m.%d")}</div>', unsafe_allow_html=True)

        st.markdown(f"""
            <div class="grid-2">
                <div class="card">
                    <div class="title-sub">정규장 종가</div>
                    <div class="val-main">₩{curr_price:,.0f}</div>
                    <div class="val-sub {"red-txt" if change_pct < 0 else "green-txt"}">{change_pct:+.2f}%</div>
                </div>
                <div class="card">
                    <div class="title-sub">52주 고점</div>
                    <div class="val-main">₩{float(df["High"].max()):,.0f}</div>
                    <div class="val-sub red-txt">고점대비 {((curr_price-float(df["High"].max()))/float(df["High"].max()))*100:.1f}%</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 📊 추세 및 모멘텀")
        st.markdown(f"""
            <div class="grid-2">
                <div class="card">
                    <div class="title-sub">이동평균 (20일)</div>
                    <div class="val-main">{"상승" if curr_price > last['MA20'] else "하락"}</div>
                    <div class="title-sub">₩{last['MA20']:,.0f}</div>
                </div>
                <div class="card">
                    <div class="title-sub">RSI (14)</div>
                    <div class="val-main">RSI {last['RSI']:.0f}</div>
                    <div class="title-sub">{"과매도" if last['RSI'] < 40 else "중립"}</div>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🎯 지지 / 저항 레벨")
        piv = (float(last['High']) + float(last['Low']) + curr_price) / 3
        st.markdown(f"""
            <div class="grid-3">
                <div class="box-sup"><div class="title-sub">지지1</div><div class="val-main">₩{(2*piv-last['High']):,.0f}</div></div>
                <div class="box-piv"><div class="title-sub">피벗</div><div class="val-main">₩{piv:,.0f}</div></div>
                <div class="box-res"><div class="title-sub">저항1</div><div class="val-main">₩{(2*piv-last['Low']):,.0f}</div></div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("#### 🤖 AI 투자 시나리오")
        st.markdown(f"""
            <div class="card">
                <div class="title-sub">전망 요약</div>
                <div style="font-size:0.95rem;"><b>단기:</b> {ai_data['short_term']}<br><b>중기:</b> {ai_data['mid_term']}</div>
            </div>
            <div class="grid-2">
                <div class="box-sup" style="text-align:left;"><b class="green-txt">🟢 강세</b><br><span style="font-size:0.8rem;">{ai_data['bull']}</span></div>
                <div class="box-res" style="text-align:left;"><b class="red-txt">🔴 약세</b><br><span style="font-size:0.8rem;">{ai_data['bear']}</span></div>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.error("데이터를 찾을 수 없습니다.")
