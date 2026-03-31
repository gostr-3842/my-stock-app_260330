import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import time
import json

# 🔑 한투 API 설정 (st.secrets에서 가져옴)
APP_KEY = st.secrets.get("KIS_APP_KEY")
APP_SECRET = st.secrets.get("KIS_APP_SECRET")
BASE_URL = "https://openapi.koreainvestment.com:9443"

@st.cache_data(ttl=80000) # 약 22시간 캐싱 (토큰 재사용)
def get_kis_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get("access_token")

@st.cache_data(ttl=600) # 10분 캐싱
def get_investor_data(symbol):
    # 티커에서 숫자만 추출 (예: 005930.KS -> 005930)
    code = "".join(filter(str.isdigit, symbol))
    token = get_kis_access_token()
    
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-investor"
    headers = {
        "content-type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010900"
    }
    params = {"FID_COND_MRKT_DIV_CODE": "J", "FID_INPUT_ISCD": code}
    
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json()['output']
        df = pd.DataFrame(data)
        # 필요한 수치들 숫자로 변환 (외인, 기관, 개인, 거래량 등)
        cols = ['stck_bsop_date', 'prdy_vrss', 'stck_prpr', 'frgn_ntby_qty', 'orgn_ntby_qty', 'ant_ntby_qty', 'acml_vol']
        for col in cols: df[col] = pd.to_numeric(df[col], errors='coerce')
        return df.head(3) # 최근 3일치만 반환
    except:
        return None

def analyze_investor_flow(df, is_mirrored=False, leader_name=""):
    if df is None or df.empty: return "수급 데이터를 불러올 수 없습니다."
    
    today = df.iloc[0]
    f_qty = today['frgn_ntby_qty'] # 외인
    o_qty = today['orgn_ntby_qty'] # 기관
    a_qty = today['ant_ntby_qty']  # 개인
    vol = today['acml_vol']        # 전체 거래량
    
    # 1. 수급 강도와 비중 계산
    f_ratio = (f_qty / vol) * 100 if vol > 0 else 0
    strength_txt = "강력 매집" if f_ratio >= 5 else ("압도적 주도" if f_ratio >= 10 else "참여 중")
    
    # 2. 수급 주체간 비교 (개인 물량 외인이 받았나?)
    swap_txt = "손바뀜 발생 포착" if a_qty < 0 and f_qty > 0 and abs(f_qty) >= abs(a_qty) * 0.7 else "혼조세"
    
    # 3. 기관과의 협력 (Twin Buy)
    twin_buy = "외인/기관 쌍끌이 매수 포착" if f_qty > 0 and o_qty > 0 else ""
    
    prefix = f"💡 [참고: 대장주 {leader_name} 미러링] " if is_mirrored else ""
    
    # 최종 요약 문장 생성
    result = f"{prefix}오늘 외국인은 전체 거래의 {abs(f_ratio):.1f}%를 차지하며 {strength_txt} 양상을 보였고, {swap_txt} 상황입니다. {twin_buy}"
    return result

@st.cache_data(ttl=600)
def load_stock_data(sym):
    # 기존 yfinance 로직 (동일)
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
