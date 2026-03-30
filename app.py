import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from groq import Groq
import json
import re

# 📱 1. 기본 설정 및 모바일 최적화 UI
st.set_page_config(page_title="AI 실시간 주식 리포트", page_icon="📈", layout="centered")

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
    .box-sup { background-color: rgba(0, 210, 106, 0.1); border: 1px solid #00d26a; border-radius: 8px; padding: 10px; text-align: center; }
    .box-res { background-color: rgba(255, 75, 75, 0.1); border: 1px solid #ff4b4b; border-radius: 8px; padding: 10px; text-align: center; }
    .box-piv { background-color: rgba(255, 170, 0, 0.1); border: 1px solid #ffaa00; border-radius: 8px; padding: 10px; text-align: center; }
    .badge { padding: 4px 10px; border-radius: 6px; font-weight: bold; font-size: 0.9rem; float: right; margin-top: 5px; }
    .badge-buy { background-color: #00d26a; color: #000; }
    .badge-sell { background-color: #ff4b4b; color: #fff; }
    .badge-hold { background-color: #4b5563; color: #fff; }
</style>
""", unsafe_allow_html=True)

# 🔍 2. 종목 검색 설정
SYMBOL_MAP = {
    "TIGER 반도체TOP10": "396500.KS", "KODEX AI반도체": "439150.KS",
    "삼성전자": "005930.KS", "SK하이닉스": "000660.KS",
    "NVDA": "NVDA", "ALAB": "ALAB", "META": "META", "MSFT": "MSFT"
}

col_search, col_btn = st.columns([4, 1])
with col_search:
    search_query = st.text_input("종목명/티커 검색", "TIGER 반도체TOP10", label_visibility="collapsed")
with col_btn:
    st.write("") # 간격 맞춤
    st.button("🔄 갱신")

clean_query = search_query.replace(" ", "").upper()
clean_map = {key.replace(" ", "").upper(): value for key, value in SYMBOL_MAP.items()}
symbol = clean_map.get(clean_query, search_query)

# 🧠 3. 하이브리드 AI 분석 엔진 (Groq + Gemini)
@st.cache_data(ttl=600)
def get_hybrid_analysis(q, curr, ma20, rsi, macd):
    prompt = f"종목:{q},가:{curr},20선:{ma20},RSI:{rsi},MACD:{macd}. JSON(decision:매수/매도/관망, short_term, mid_term, bull, bear). 한국어 답변."
    
    # 1단계: Groq
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-specdec",
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except: pass

    # 2단계: Gemini
    gemini_keys = [st.secrets.get("GEMINI_API_KEY_1"), st.secrets.get("GEMINI_API_KEY_2")]
    for k in [gk for gk in gemini_keys if gk]:
        try:
            genai.configure(api_key=k)
            for m_name in ['gemini-2.0-flash', 'gemini-1.5-flash']:
                try:
                    model = genai.GenerativeModel(m_name)
                    res = model.generate_content(prompt)
                    jt = re.sub(r'```[a-zA-Z]*\n|```', '', res.text).strip()
                    return json.loads(jt[jt.find('{'):jt.rfind('}')+1])
                except: continue
        except: continue
    return None

# 📊 4. 데이터 로드 보강 (야후 파이낸스 차단 우회 로직)
with st.spinner(f"'{symbol}' 데이터 분석 중..."):
    import time
    
    df = None
    # 3번까지 재시도 (야후 차단 대비)
    for i in range(3):
        try:
            df = yf.download(symbol, period="1y", interval="1d", progress=False, timeout=10)
            if df is not None and not df.empty:
                break
            time.sleep(1) # 1초 쉬었다가 다시 시도
        except:
            time.sleep(1)
            continue
            
    if df is not None and not df.empty:
        # 멀티인덱스 컬럼 정리
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # 데이터가 가끔 float으로 안 들어오는 경우 대비
        df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
        df = df.dropna(subset=['Close']) # 빈 데이터 삭제

        # --- 이후 지표 계산 로직은 동일 ---
        df['MA20'] = df['Close'].rolling(20).mean()
        # ... (이후 코드 생략, 기존과 동일) ...
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain/loss)))
        df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
        
        last = df.iloc[-1]
        curr_price = float(last['Close'])
        prev_price = float(df.iloc[-2]['Close'])
        change_pct = ((curr_price - prev_price) / prev_price) * 100
        
        ai_res = get_hybrid_analysis(search_query, curr_price, float(last['MA20']), float(last['RSI']), float(last['MACD']))
        if not ai_res:
            ai_res = {"decision":"확인불가", "short_term":"API 한도 초과", "mid_term":"잠시 후 시도", "bull":"-", "bear":"-"}

        # 🖥️ 5. UI 렌
