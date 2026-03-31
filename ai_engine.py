import streamlit as st
from google import genai
from groq import Groq
import json
import re

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
