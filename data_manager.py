import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

# 한투 실전투자 고정 URL
KIS_URL = "https://openapi.koreainvestment.com:9443"

def get_api_keys():
    """금고에서 API 키를 안전하게 가져옵니다."""
    app_key = st.secrets.get("KIS_APP_KEY", None)
    app_secret = st.secrets.get("KIS_APP_SECRET", None)
    return app_key, app_secret

def get_access_token():
    app_key, app_secret = get_api_keys()
    if not app_key or not app_secret:
        return None
        
    if 'access_token' in st.session_state and datetime.now() < st.session_state.get('token_expiry', datetime.min):
        return st.session_state['access_token']
    
    url = f"{KIS_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        return None
        
    data = res.json()
    st.session_state['access_token'] = data.get('access_token')
    st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=int(data.get('expires_in', 86400)) - 3600)
    return st.session_state['access_token']

def safe_int(val):
    """[핵심 방어막] 어떤 쓰레기 값(NaN, Null, 빈문자열)이 들어와도 안전하게 0으로 변환하는 함수"""
    try:
        num = pd.to_numeric(val, errors='coerce')
        if pd.isna(num):
            return 0
        return int(num)
    except:
        return 0

@st.cache_data(ttl=300)
def get_market_status():
    """상단 바를 위한 시장 지수 및 외인 수급 데이터"""
    token = get_access_token()
    app_key, app_secret = get_api_keys()
    
    if not token or not app_key:
        return {"KOSPI": 0, "KOSDAQ": 0, "FUTURES": 0, "ERROR": True}

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST03010300"
    }
    
    results = {"ERROR": False}
    for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
        params = {"fid_input_iscd": code}
        res = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-trend-per-market", headers=headers, params=params)
        if res.status_code == 200:
            output = res.json().get('output', {})
            # safe_int를 적용하여 야간 NaN 에러 원천 차단
            amt = safe_int(output.get('frgn_ntby_amt', 0))
            results[name] = int(amt / 100)
        else:
            results[name] = 0
            
    results['FUTURES'] = results.get('KOSPI', 0) * 2 
    return results

@st.cache_data(ttl=300)
def load_stock_data(symbol):
    """주식 차트 데이터 및 RSI 계산"""
    import yfinance as yf
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo", interval="1d")
        if df.empty: return None, None
        
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        fetch_time = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
        return df, fetch_time
    except:
        return None, None

@st.cache_data(ttl=300)
def get_investor_data(symbol):
    """[핵심 로직] 시간에 따른 라우팅 및 잠정치 덮어쓰기"""
    token = get_access_token()
    app_key, app_secret = get_api_keys()
    
    if not token or not app_key:
        return None
        
    iscd = symbol.split('.')[0]
    now = datetime.now(timezone(timedelta(hours=9)))
    
    # 09:00 ~ 15:30 사이인지 체크 (장중 스위치)
    is_market_open = (9 <= now.hour <= 14) or (now.hour == 15 and now.minute <= 30)
    
    # 일별 '확정치' 기본 호출
    headers_daily = {
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010900"
    }
    res_daily = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-investor", headers=headers_daily, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": iscd})
    
    if res_daily.status_code == 200:
        data = res_daily.json().get('output', [])
        df = pd.DataFrame(data)
        
        if not df.empty:
            # 장중일 때만 '잠정치'를 찔러서 업데이트 시도
            if is_market_open:
                headers_temp = {
                    "authorization": f"Bearer {token}",
                    "appkey": app_key,
                    "appsecret": app_secret,
                    "tr_id": "FHKST01010500"
                }
                res_temp = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-opertn-time", headers=headers_temp, params={"fid_input_iscd": iscd})
                
                if res_temp.status_code == 200:
                    temp_val = safe_int(res_temp.json().get('output', {}).get('frgn_ntby_qty', 0))
                    # 잠정치가 빈칸이 아니고 0도 아니라면 오늘 행(0번)에 덮어쓰기
                    if temp_val != 0:
                        df.iloc[0, df.columns.get_loc('frgn_ntby_qty')] = temp_val
            return df
    return None

def analyze_investor_flow(df, is_mirrored, ref_name):
    if df is None or df.empty: return "수급 데이터 분석 불가"
    
    # safe_int를 적용하여 NaN 에러 차단
    recent_flows = [safe_int(x) for x in df['frgn_ntby_qty'].head(3)]
    net_sum = sum(recent_flows)
    
    msg = "[수급] "
    if is_mirrored: msg += f"({ref_name} 참고) "
    
    if net_sum > 100000: msg += "외국인 강력 매수세 유입 중. 긍정적 시그널."
    elif net_sum < -100000: msg += "외국인 대량 매도 포착. 리스크 관리 필요."
    else: msg += "외국인 수급 관망세. 뚜렷한 방향성 없음."
    return msg