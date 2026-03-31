import streamlit as st
from google import genai
from groq import Groq
import json
import re

@st.cache_data(ttl=600)
def get_ai_scenarios(q, curr, rsi, supply_text, macro_keyword=""):
    # 사용자가 시장 상황을 입력했다면 프롬프트에 강력하게 주입합니다.
    macro_context = f"\n[핵심 전제 조건] 현재 거시경제/시장 상황: {macro_keyword}\n(분석 시 이 상황을 최우선으로 반영하여 보수적/공격적 스탠스를 결정할 것.)" if macro_keyword else ""
    
    prompt = f"""당신은 탑티어 증권사 수석 애널리스트입니다.
    종목: {q}, 현재가: {curr}, RSI: {rsi:.1f}
    최신 수급 동향: {supply_text}{macro_context}
    
    위 데이터를 바탕으로 반드시 JSON 포맷으로 아래 5개 항목을 작성하세요.
    - decision: '매수', '매도', '관망' 중 1개 (수급과 거시경제가 안 좋으면 RSI가 낮아도 관망/매도로 판정)
    - short_term: 수급과 거시경제를 반영한 단기 예측 (2~3문장)
    - mid_term: 중기 펀더멘탈 및 시황 (2~3문장)
    - bull: 상승 모멘텀 (긍정 요소)
    - bear: 하락 리스크 (거시경제 악재 및 수급 부정 요소 포함)
    한국어로 전문적인 톤으로 작성하세요."""
    
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
