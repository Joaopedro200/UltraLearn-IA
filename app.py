#!/usr/bin/env python3
"""UltraLearn IA – deploy pronto"""
import streamlit as st
import json, os
from datetime import datetime, timedelta
from groq import Groq

st.set_page_config(page_title="UltraLearn IA", page_icon="🧠", layout="centered")

def inject_css():
    st.markdown("""<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html,body,[class*="css"]{font-family:'Inter',sans-serif}
    .main-header{background:linear-gradient(135deg,#1e293b,#0f172a);padding:2rem;border-radius:16px;margin-bottom:2rem;border:1px solid rgba(255,255,255,0.08)}
    .main-header h1{color:#f8fafc;font-size:2.5rem}
    .explanation-box{background:#0f172a;border:1px solid #334155;border-radius:16px;padding:2rem;color:#e2e8f0}
    .primata-box{background:#fef3c7;border:2px solid #f59e0b;border-radius:20px;padding:2rem;color:#78350f;position:relative}
    .primata-box::before{content:"🐵";font-size:3rem;position:absolute;top:-20px;left:20px}
    .quiz-card{background:#1e293b;border-radius:16px;padding:2rem;margin:1rem 0;box-shadow:0 4px 20px rgba(0,0,0,0.3)}
    div.stButton>button{border-radius:10px;font-weight:600;padding:0.6rem 2rem;border:none;background:linear-gradient(135deg,#3b82f6,#2563eb);color:white}
    </style>""", unsafe_allow_html=True)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    st.error("Chave da API não configurada.")
    st.stop()
client = Groq(api_key=GROQ_API_KEY)

# -- Estados da sessão --
for k in ["explanation","topic","primata_explanation","quiz_questions","quiz_index","quiz_score","quiz_active","quiz_feedback"]:
    if k not in st.session_state: st.session_state[k] = "" if k in ["explanation","topic","primata_explanation"] else ([] if k=="quiz_questions" else (0 if k in ["quiz_index","quiz_score"] else (False if k=="quiz_active" else None)))

def gen_explanation(t):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Explique '{t}' em português, 3 parágrafos detalhados."}], temperature=0.7, max_tokens=1500)
    return resp.choices[0].message.content.strip()

def gen_primata(t):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Macaco professor explica '{t}' em português, aula completa e divertida, 5+ parágrafos."}], temperature=0.9, max_tokens=2500)
    return resp.choices[0].message.content.strip()

def gen_quiz(text, diff, num):
    dmap = {"fácil":"fácil","médio":"médio","difícil":"difícil"}
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Crie {num} perguntas em português ({dmap[diff]}) sobre: {text}. JSON com 'questions'."}], temperature=0.7, max_tokens=2000)
    cont = resp.choices[0].message.content.strip()
    if cont.startswith("```"): cont = cont[cont.find("\n"):].rstrip("```").strip()
    try: return json.loads(cont).get("questions", [])
    except: return []

def show_quiz():
    idx = st.session_state.quiz_index
    total = len(st.session_state.quiz_questions)
    if idx >= total:
        st.balloons(); st.success(f"Quiz concluído! Acertos: {st.session_state.quiz_score}/{total}")
        if st.button("Limpar Quiz"): st.session_state.quiz_questions=[]; st.session_state.quiz_index=0; st.rerun()
        return
    q = st.session_state.quiz_questions[idx]
    st.progress(idx/total); st.caption(f"Questão {idx+1}/{total}")
    with st.container():
        st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
        st.subheader(q['question'])
        if q['type']=="multiple_choice":
            opt = st.radio("Opções", q['options'], index=None)
            if st.button("Responder") and opt:
                user = opt.split('.')[0].strip()
                correct = q['correct_answer']
                if user==correct: st.session_state.quiz_score+=1; st.session_state.quiz_feedback=(True,correct,q['explanation'])
                else: st.session_state.quiz_feedback=(False,correct,q['explanation'])
                st.session_state.quiz_index+=1; st.rerun()
        else:
            opt = st.radio("V/F", ["Verdadeiro","Falso"], index=None)
            if st.button("Responder") and opt:
                user = "Verdadeiro" if opt=="Verdadeiro" else "Falso"
                correct = q['correct_answer']
                if user==correct: st.session_state.quiz_score+=1; st.session_state.quiz_feedback=(True,correct,q['explanation'])
                else: st.session_state.quiz_feedback=(False,correct,q['explanation'])
                st.session_state.quiz_index+=1; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.quiz_feedback:
        a,c,e = st.session_state.quiz_feedback
        st.markdown(f'<div class="feedback-{"correct" if a else "incorrect"}">{"✅" if a else "❌"} {e}</div>', unsafe_allow_html=True)
        st.session_state.quiz_feedback=None

def main():
    inject_css()
    st.markdown('<div class="main-header"><h1>🧠 UltraLearn IA</h1><p>Aprenda com estilo!</p></div>', unsafe_allow_html=True)
    tab1,tab2,tab3 = st.tabs(["📖 Ensinar","🧠 Quiz","🐵 Primata"])
    with tab1:
        topic = st.text_input("Assunto:", key="topic")
        if st.button("Gerar Explicação"):
            if topic: st.session_state.explanation = gen_explanation(topic); st.rerun()
        if st.session_state.explanation:
            st.markdown(f'<div class="explanation-box">{st.session_state.explanation}</div>', unsafe_allow_html=True)
            d = st.selectbox("Dificuldade",["Fácil","Médio","Difícil"],index=1)
            n = st.number_input("Perguntas",1,20,5)
            if st.button("Criar Quiz"):
                st.session_state.quiz_questions = gen_quiz(st.session_state.explanation, d, n)
                st.session_state.quiz_index = 0; st.rerun()
    with tab2:
        if st.session_state.quiz_active and st.session_state.quiz_questions:
            show_quiz()
        else:
            st.info("Crie um quiz na aba Ensinar primeiro.")
    with tab3:
        pt = st.text_input("Tópico primata:", key="ptopic")
        if st.button("Macaco Sábio"):
            if pt: st.session_state.primata_explanation = gen_primata(pt); st.rerun()
        if st.session_state.primata_explanation:
            st.markdown(f'<div class="primata-box">{st.session_state.primata_explanation}</div>', unsafe_allow_html=True)

if __name__=="__main__":
    main()
