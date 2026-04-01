import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta, timezone

# 한투 실전투자 고정 URL (에러 해결 핵심)
KIS_URL = "https://openapi.koreainvestment.com:9443"

# 세션 관리 및 토큰 발급
def get_access_token():
    if 'access_token' in st.session_state and datetime.now() < st.session_state.get('token_expiry', datetime.min):
        return st.session_state['access_token']
    
    url = f"{KIS_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": st.secrets['app_key'],
        "appsecret": st.secrets['app_secret']
    }
    res = requests.post(url, json=payload)
    data = res.json()
    
    st.session_state['access_token'] = data['access_token']
    st.session_state['token_expiry'] = datetime.now() + timedelta(seconds=int(data.get('expires_in', 86400)) - 3600)
    return data['access_token']

# 5분 캐시 적용 (TTL=300)
@st.cache_data(ttl=300)
def get_market_status():
    """상단 바를 위한 시장 지수 및 외인 수급 데이터"""
    token = get_access_token()
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": st.secrets['app_key'],
        "appsecret": st.secrets['app_secret'],
        "tr_id": "FHKST03010300" # 투자자별 매매동향(시장)
    }
    
    # 코스피(0001), 코스닥(1001) 수급 가져오기
    results = {}
    for code, name in [("0001", "KOSPI"), ("1001", "KOSDAQ")]:
        params = {"fid_input_iscd": code}
        res = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-trend-per-market", headers=headers, params=params)
        if res.status_code == 200:
            output = res.json().get('output', {})
            # 외국인 순매수 금액 (단위: 억)
            results[name] = int(int(output.get('frgn_ntby_amt', 0)) / 100)
        else:
            results[name] = 0
            
    # 선물 수급 (KOSPI 수급 기반 추정치 - 향후 선물 전용 TR 연동 전까지 앱이 죽지 않도록 방어 로직 적용)
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
        
        # RSI 계산
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
    """잠정치 및 확정치 수급 데이터 통합"""
    token = get_access_token()
    iscd = symbol.split('.')[0]
    
    # 1. 먼저 장중 '잠정치' 시도 (FHKST01010500)
    headers_temp = {
        "authorization": f"Bearer {token}",
        "appkey": st.secrets['app_key'],
        "appsecret": st.secrets['app_secret'],
        "tr_id": "FHKST01010500" # 종목별 투자자 잠정치
    }
    res_temp = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/investor-opertn-time", headers=headers_temp, params={"fid_input_iscd": iscd})
    
    # 2. 일별 '확정치' (FHKST01010900)
    headers_daily = {
        "authorization": f"Bearer {token}",
        "appkey": st.secrets['app_key'],
        "appsecret": st.secrets['app_secret'],
        "tr_id": "FHKST01010900"
    }
    res_daily = requests.get(f"{KIS_URL}/uapi/domestic-stock/v1/quotations/inquire-investor", headers=headers_daily, params={"fid_cond_mrkt_div_code": "J", "fid_input_iscd": iscd})
    
    if res_daily.status_code == 200:
        data = res_daily.json().get('output', [])
        df = pd.DataFrame(data)
        if not df.empty:
            # 잠정치가 있고 장 중(+0이 아님)이라면 첫 번째 행에 덮어쓰기
            if res_temp.status_code == 200:
                temp_val = res_temp.json().get('output', {}).get('frgn_ntby_qty', 0)
                if temp_val and int(temp_val) != 0:
                    df.iloc[0, df.columns.get_loc('frgn_ntby_qty')] = temp_val
            return df
    return None

def analyze_investor_flow(df, is_mirrored, ref_name):
    if df is None or df.empty: return "수급 데이터 분석 불가"
    
    recent_flows = [int(x) if pd.notna(x) else 0 for x in df['frgn_ntby_qty'].head(3)]
    net_sum = sum(recent_flows)
    
    msg = "[수급] "
    if is_mirrored: msg += f"({ref_name} 참고) "
    
    if net_sum > 100000: msg += "외국인 강력 매수세 유입 중. 긍정적 시그널."
    elif net_sum < -100000: msg += "외국인 대량 매도 포착. 리스크 관리 필요."
    else: msg += "외국인 수급 관망세. 뚜렷한 방향성 없음."
    return msg
