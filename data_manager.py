import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

# 한투 실전투자 고정 URL
KIS_URL = "https://openapi.koreainvestment.com:9443"

def get_api_keys():
    """금고에서 KIS_APP_KEY와 KIS_APP_SECRET을 정확하게 가져옵니다."""
    app_key = st.secrets.get("KIS_APP_KEY", None)
    app_secret = st.secrets.get("KIS_APP_SECRET", None)
    return app_key, app_secret

def get_access_token():
    app_key, app_secret = get_api_keys()
    if not app_key or not app_secret:
        return None # 키가 없으면 토큰 발급 중단
        
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
    # 토큰 만료 시간 안전하게 설정 (기본 24시간 - 1시간 여유)
    st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=int(data.get('expires_in', 86400)) - 3600)
    return st.session_state['access_token']

@st.cache_data(ttl=300)
def get_market_status():
    """상단 바를 위한 시장 지수 및 외인 수급 데이터 (5분 자동 갱신)"""
    token = get_access_token()
    app_key, app_secret = get_api_keys()
    
    # 토큰이나 키가 없으면 기본값 반환하여 앱 다운 방지
    if not token or not app_key:
        return {"KOSPI": 0, "KOSDAQ": 0, "FUTURES": 0, "ERROR": True}

    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST03010300" # 투자자별 매매동향(시장)
    }
    
    results = {"ERROR": False}
    for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
        params = {"fid_input_iscd": code}
        res = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-trend-per-market", headers=headers, params=params)
        if res.status_code == 200:
            output = res.json().get('output', {})
            results[name] = int(int(output.get('frgn_ntby_amt', 0)) / 100)
        else:
            results[name] = 0
            
    # 선물 수급 추정치 방어 로직 (추후 진짜 선물 TR 연동 전까지 야간에도 에러 안 나도록 방어)
    results['FUTURES'] = results.get('KOSPI', 0) * 2 
    return results

@st.cache_data(ttl=300)
def load_stock_data(symbol):
    """주식 차트 데이터 및 RSI 계산 (5분 단위 갱신)"""
    import yfinance as yf
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1mo", interval="1d")
        if df.empty: return None, None
        
        # RSI 14일선 계산
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # 20일 이동평균선
        df['MA20'] = df['Close'].rolling(window=20).mean()
        
        # 현재 시간 마킹 (KST)
        fetch_time = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d %H:%M:%S")
        return df, fetch_time
    except:
        return None, None

@st.cache_data(ttl=300)
def get_investor_data(symbol):
    """잠정치 및 확정치 수급 데이터 통합 로직"""
    token = get_access_token()
    app_key, app_secret = get_api_keys()
    
    if not token or not app_key:
        return None
        
    iscd = symbol.split('.')[0]
    
    # 1. 장중 4회 갱신되는 '잠정치' 먼저 찌르기
    headers_temp = {
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010500" # 종목별 잠정치 API
    }
    res_temp = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-opertn-time", headers=headers_temp, params={"fid_input_iscd": iscd})
    
    # 2. 일별 '확정치' 가져오기
    headers_daily = {
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01010900" # 일별 투자자 API
    }
    res_daily = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-investor", headers=headers_daily, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": iscd})
    
    if res_daily.status_code == 200:
        data = res_daily.json().get('output', [])
        df = pd.DataFrame(data)
        if not df.empty:
            # 잠정치 통신이 성공했고, 값이 0이 아니라면 오늘 날짜 최상단에 덮어쓰기
            if res_temp.status_code == 200:
                temp_val = res_temp.json().get('output', {}).get('frgn_ntby_qty', 0)
                if temp_val and int(temp_val) != 0:
                    df.iloc[0, df.columns.get_loc('frgn_ntby_qty')] = temp_val
            return df
    return None

def analyze_investor_flow(df, is_mirrored, ref_name):
    """수급 데이터 텍스트 요약 (AI에게 넘길 용도)"""
    if df is None or df.empty: return "수급 데이터 분석 불가"
    
    recent_flows = [int(pd.to_numeric(x, errors='coerce')) if pd.notna(x) else 0 for x in df['frgn_ntby_qty'].head(3)]
    net_sum = sum(recent_flows)
    
    msg = "[수급] "
    if is_mirrored: msg += f"({ref_name} 참고) "
    
    if net_sum > 100000: msg += "외국인 강력 매수세 유입 중. 긍정적 시그널."
    elif net_sum < -100000: msg += "외국인 대량 매도 포착. 리스크 관리 필요."
    else: msg += "외국인 수급 관망세. 뚜렷한 방향성 없음."
    return msg
