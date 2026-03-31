import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import json

APP_KEY = st.secrets.get("KIS_APP_KEY")
APP_SECRET = st.secrets.get("KIS_APP_SECRET")
BASE_URL = "https://openapi.koreainvestment.com:9443"

@st.cache_data(ttl=80000)
def get_kis_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get("access_token")

@st.cache_data(ttl=600)
def get_investor_data(symbol):
    code = "".join(filter(str.isdigit, symbol))
    token = get_kis_access_token()
    
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010900",
        "custtype": "P" # KIS 정책상 개인(P) 헤더가 필요할 수 있어 추가함
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    
    try:
        res = requests.get(url, headers=headers, params=params)
        
        # 🚨 [디버그 추가] 한투가 에러를 뱉으면 화면에 띄웁니다
        json_data = res.json()
        if 'output' not in json_data:
            st.error(f"🛑 한투 API 거절 사유: {res.text}")
            return None
        # --------------------------------------------------
            
        data = json_data['output']
        df = pd.DataFrame(data)
        cols = ['stck_bsop_date', 'prdy_vrss', 'stck_prpr', 'frgn_ntby_qty', 'orgn_ntby_qty', 'ant_ntby_qty', 'acml_vol']
        for col in cols: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.head(3)
    except Exception as e:
        st.error(f"🛑 처리 중 에러 발생: {e}")
        return None

def analyze_investor_flow(df, is_mirrored=False, leader_name=""):
    if df is None or df.empty: return "수급 데이터를 불러올 수 없습니다."
    
    today = df.iloc[0]
    f_qty = today['frgn_ntby_qty']
    o_qty = today['orgn_ntby_qty']
    a_qty = today['ant_ntby_qty']
    vol = today['acml_vol']
    
    f_ratio = (f_qty / vol) * 100 if vol > 0 else 0
    strength_txt = "강력 매집" if f_ratio >= 5 else ("압도적 주도" if f_ratio >= 10 else "참여 중")
    swap_txt = "손바뀜 발생 포착" if a_qty < 0 and f_qty > 0 and abs(f_qty) >= abs(a_qty) * 0.7 else "혼조세"
    twin_buy = "외인/기관 쌍끌이 매수 포착" if f_qty > 0 and o_qty > 0 else ""
    
    prefix = f"💡 [참고: 대장주 {leader_name} 미러링] " if is_mirrored else ""
    result = f"{prefix}오늘 외국인은 전체 거래의 {abs(f_ratio):.1f}%를 차지하며 {strength_txt} 양상을 보였고, {swap_txt} 상황입니다. {twin_buy}"
    return result

@st.cache_data(ttl=600)
def load_stock_data(sym):
    for i in range(3):
        try:
            tkr = yf.Ticker(sym)
            df = tkr.history(period="1y", interval="1d")
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                df['Close'] = pd.to_numeric(df['Close'], errors='coerce'); df = df.dropna(subset=['Close'])
                df['MA20'] = df['Close'].rolling(20).mean(); df['MA50'] = df['Close'].rolling(50).mean()
                delta = df['Close'].diff()
                gain = (delta.where(delta > 0, 0)).rolling(14).mean(); loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                df['RSI'] = 100 - (100 / (1 + (gain/loss)))
                df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
                df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
                return df
        except: time.sleep(1)
    return None
