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

def format_price(val, sym):
    if ".KS" in sym or ".KQ" in sym: return f"₩{val:,.0f}"
    return f"${val:,.2f}"

# 🔍 2. 스마트 검색창 (CSV 기반)
@st.cache_data
def load_tickers():
    try:
        return pd.read_csv("krx_tickers.csv")
    except Exception:
        return pd.DataFrame(columns=["name", "ticker"])

df_tickers = load_tickers()

col_search, col_btn = st.columns([4, 1])
with col_search:
    query = st.text_input("종목 검색", "", placeholder="예: 삼성전자, 반도체, NVDA", label_visibility="collapsed")
with col_btn:
    st.button("🔄 갱신")

if query:
    clean_query = query.replace(" ", "").upper()
    mask = df_tickers["name"].astype(str).str.replace(" ", "").str.upper().str.contains(clean_query, na=False)
    results = df_tickers[mask]

    if not results.empty:
        selected_name = st.selectbox("👇 검색 결과에서 선택하세요", results["name"].tolist())
        symbol = results[results["name"] == selected_name]["ticker"].values[0]
        search_query = selected_name
    else:
        symbol = query.upper()
        search_query = query.upper()
else:
    symbol = "396500.KS"
    search_query = "TIGER FN반도체TOP10"

# 🤖 3. 상세 AI 리포팅 엔진 (강력한 프롬프트 적용)
@st.cache_data(ttl=600)
def get_ai_scenarios(q, curr, rsi):
    prompt = f"""당신은 탑티어 증권사 수석 애널리스트입니다.
    종목: {q}, 현재가: {curr}, RSI: {rsi:.1f}
    반드시 JSON 포맷으로 아래 5개 항목을 작성하세요.
    - decision: '매수', '매도', '관망' 중 딱 1개 선택
    - short_term: 단기(1~2주) 가격 흐름과 지지/저항선 예측 (반드시 2~3문장의 구체적 서술)
    - mid_term: 중기(1~3개월) 펀더멘탈, 시황 전망 (반드시 2~3문장의 구체적 서술)
    - bull: 상승을 견인할 모멘텀 및 호재 (구체적 이유 2~3문장 서술)
    - bear: 하락을 유발할 리스크 및 악재 (구체적 이유 2~3문장 서술)
    모든 답변은 한국어로 전문적인 톤으로 작성하세요."""
    
    groq_key = st.secrets.get("GROQ_API_KEY")
    if groq_key:
        try:
            client = Groq(api_key=groq_key)
            completion = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}], 
                model="llama-3.3-70b-versatile", 
                response_format={"type": "json_object"}
            )
            return json.loads(completion.choices[0].message.content)
        except: pass

    gemini_keys = [st.secrets.get("GEMINI_API_KEY_1"), st.secrets.get("GEMINI_API_KEY_2")]
    for k in [gk for gk in gemini_keys if gk]:
        try:
            client = genai.Client(api_key=k)
            res = client.models.generate_content(model='gemini-2.0-flash', contents=prompt)
            jt = re.sub(r'```[a-zA-Z]*\n|```', '', res.text).strip()
            return json.loads(jt[jt.find('{'):jt.rfind('}')+1])
        except: continue
    return {"decision":"관망", "short_term":"분석 로딩 중...", "mid_term":"잠시 후 다시 시도하세요.", "bull":"-", "bear":"-"}

# 🛡️ 4. 데이터 로드
@st.cache_data(ttl=600)
def load_stock_data(sym):
    for i in range(3):
        try:
            tkr = yf.Ticker(sym)
            df = tkr.history(period="1y", interval="1d")
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce')
                df = df.dropna(subset=['Close'])
                df['MA20'] = df['Close'].rolling(20).mean()
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                df['RSI'] = 100 - (100 / (1 + (gain/loss)))
                return df
        except: time.sleep(1)
    return None

# 📊 5. 렌더링
with st.spinner(f"분석 중..."):
    df = load_stock_data(symbol)
    if df is not None:
        last = df.iloc[-1]
        curr_price = float(last['Close'])
        rsi_val = last['RSI'] if not pd.isna(last['RSI']) else 50
        ai_data = get_ai_scenarios(search_query, curr_price, rsi_val)
        
        decision = ai_data.get('decision', '관망')
        badge_cls = "badge-buy" if decision == "매수" else ("badge-sell" if decision == "매도" else "badge-hold")

        st.markdown(f'<span class="badge {badge_cls}">{decision}</span><h2 style="margin:0;">{search_query} <br><span style="font-size:1rem;color:#6b7280;font-weight:normal;">{symbol}</span></h2>', unsafe_allow_html=True)
        
        change_pct = ((curr_price - float(df.iloc[-2]['Close'])) / float(df.iloc[-2]['Close'])) * 100
        st.markdown(f"""
        <div class="grid-2" style="margin-top:25px;">
            <div class="vip-card">
                <div class="card-title">현재가</div>
                <div class="top-price-val">{format_price(curr_price, symbol)}</div>
                <div class="{"txt-red" if change_pct < 0 else "txt-green"}">{change_pct:+.2f}%</div>
            </div>
            <div class="vip-card">
                <div class="card-title">RSI (14)</div>
                <div class="top-price-val" style="font-size:1.6rem;">{rsi_val:.0f}</div>
                <div class="{"txt-green" if rsi_val < 30 else ("txt-red" if rsi_val > 70 else "txt-yellow")}">{"과매도" if rsi_val < 30 else ("과매수" if rsi_val > 70 else "중립")}</div>
            </div>
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
    else:
        st.error("데이터 로드 실패")
