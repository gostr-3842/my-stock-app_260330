import pandas as pd
import streamlit as st
import os

def format_price(val, symbol):
    if ".KS" in symbol or ".KQ" in symbol:
        return f"{int(val):,}원"
    return f"${val:.2f}"

@st.cache_data
def load_tickers():
    file_name = "krx_tickers.csv"
    
    # 1. 파일 존재 여부 1차 방어
    if not os.path.exists(file_name):
        st.error(f"🚨 '{file_name}' 파일을 찾을 수 없습니다. Streamlit Cloud에 파일이 정확히 업로드되었는지 확인해주세요.")
        return pd.DataFrame(columns=["ticker", "name"])
        
    # 2. 인코딩 에러 2차 방어 (utf-8 먼저 시도 후, 윈도우 엑셀용 cp949 시도)
    try:
        df = pd.read_csv(file_name, encoding="utf-8")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(file_name, encoding="cp949")
        except Exception as e:
            st.error(f"🚨 CSV 인코딩 에러가 발생했습니다. 파일을 utf-8로 다시 저장해주세요: {e}")
            return pd.DataFrame(columns=["ticker", "name"])
    except Exception as e:
        st.error(f"🚨 CSV 파일을 읽는 중 알 수 없는 에러가 발생했습니다: {e}")
        return pd.DataFrame(columns=["ticker", "name"])
        
    # 3. 컬럼명 3차 방어 (공백 제거 및 소문자 통일)
    df.columns = df.columns.str.strip().str.lower()
    
    # 한글 컬럼명(종목코드, 종목명)으로 되어 있을 경우 영어로 강제 매핑
    if "종목코드" in df.columns and "종목명" in df.columns:
        df = df.rename(columns={"종목코드": "ticker", "종목명": "name"})
        
    # 필수 컬럼(ticker, name)이 최종적으로 존재하는지 검증
    if "ticker" not in df.columns or "name" not in df.columns:
        st.error("🚨 CSV 파일 안에 'ticker'와 'name' (또는 '종목코드', '종목명') 컬럼이 없습니다. 엑셀 제목 줄을 확인해주세요.")
        return pd.DataFrame(columns=["ticker", "name"])
        
    # 종목코드가 문자열로 들어오도록 보장 (예: 005930 앞의 0이 날아가는 현상 방지)
    df['ticker'] = df['ticker'].astype(str).str.zfill(6)
    
    # 만약 '.KS' 나 '.KQ'가 안 붙어있다면 야후파이낸스 규격에 맞게 붙여주는 로직 (선택적)
    # 여기서는 원본 CSV에 .KS, .KQ가 잘 붙어있다고 가정합니다.
    
    return df
