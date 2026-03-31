import pandas as pd
import streamlit as st

def format_price(val, sym):
    if ".KS" in sym or ".KQ" in sym: return f"₩{val:,.0f}"
    return f"${val:,.2f}"

@st.cache_data
def load_tickers():
    try:
        return pd.read_csv("krx_tickers.csv")
    except Exception:
        return pd.DataFrame(columns=["name", "ticker"])
