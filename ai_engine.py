import streamlit as st
from google import genai
from groq import Groq
import json
import re

@st.cache_data(ttl=600)
def get_ai_scenarios(q, curr, rsi, supply_text):
    # 수급 분석 로직을 프롬프트에 추가
    prompt = f"""당신은 탑티어 증권사 수석 애널리스트입니다.
    종목: {q}, 현재가: {curr}, RSI: {rsi:.1f}
    최신 수급 동향: {supply_text}
    
    위 데이터를 바탕으로 반드시 JSON 포맷으로 아래 5개 항목을 작성하세요.
    - decision: '매수', '매도', '관망' 중 1개
    - short_term: 수급 상황을 반영한 단기 예측 (2~3문장)
    - mid_term: 중기 펀더멘탈 및 시황 (2~3문장)
    - bull: 상승 모멘텀 (수급 긍정 요소 포함)
    - bear: 하락 리스크 (수급 부정 요소 포함)
    한국어로 전문적인 톤으로 작성하세요."""
    
    # Groq -> Gemini 순서로 호출 로직 (기존과 동일)
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
    return {"decision":"관망", "short_term":"분석 중...", "mid_term":"잠시 후 시도", "bull":"-", "bear":"-"}
