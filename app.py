#!/usr/bin/env python3
"""
UltraLearn IA – Titanium Edition com LOGIN e RANKING GLOBAL
"""
import streamlit as st
import json, os, random, io, base64, hashlib
from datetime import datetime, timedelta, date
from groq import Groq
from gtts import gTTS
from fpdf import FPDF
import libsql
import graphviz
import PyPDF2
import pytesseract
from PIL import Image
import wikipedia
import plotly.express as px
import pandas as pd

# ---------- Configuração da página ----------
st.set_page_config(page_title="UltraLearn IA", page_icon="🧠", layout="centered")

# ---------- Conexão com Turso ----------
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
if not TURSO_URL or not TURSO_TOKEN:
    st.error("Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN nos Secrets do Streamlit Cloud.")
    st.stop()

conn = libsql.connect("ultralearn.db", sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
conn.sync()

# ---------- Criação das tabelas ----------
conn.execute("PRAGMA foreign_keys = ON")

conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        avatar TEXT DEFAULT '🧑',
        bio TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS user_data (
        user_id TEXT PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        streak INTEGER DEFAULT 0,
        last_daily TEXT,
        achievements TEXT DEFAULT '[]',
        titulos TEXT DEFAULT '[]'
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        question TEXT,
        type TEXT,
        options TEXT,
        correct_answer TEXT,
        explanation TEXT,
        interval INTEGER DEFAULT 1,
        ease_factor REAL DEFAULT 2.5,
        next_review TEXT
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS xp_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        date TEXT,
        xp_gained INTEGER
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        topic TEXT,
        quizzes INTEGER DEFAULT 0,
        errors INTEGER DEFAULT 0
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS challenges (
        id TEXT PRIMARY KEY,
        quiz_json TEXT,
        creator_user_id TEXT
    )
""")

# Migração: adiciona coluna 'titulos' se não existir (para bancos antigos)
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN titulos TEXT DEFAULT '[]'")
    conn.commit()
except:
    pass  # já existe

conn.commit()

# ---------- Funções de autenticação ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def criar_usuario(user_id, password, avatar="🧑", bio=""):
    """Retorna True se criado com sucesso, False se já existir."""
    existente = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if existente:
        return False
    pwd_hash = hash_password(password)
    conn.execute("INSERT INTO users (user_id, password_hash, avatar, bio) VALUES (?, ?, ?, ?)",
                 (user_id, pwd_hash, avatar, bio))
    conn.commit()
    conn.execute("INSERT INTO user_data (user_id) VALUES (?)", (user_id,))
    conn.commit()
    return True

def login_usuario(user_id, password):
    """Retorna True se a senha estiver correta."""
    row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return False
    return row[0] == hash_password(password)

def user_exists(user_id):
    return conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is not None

# ---------- CSS customizado ----------
def inject_css(theme="dark", font_size=16, daltonic=None):
    if theme == "dark":
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#0f172a", "#e2e8f0", "#1e293b", "#fef3c7", "#78350f",
            "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)", "linear-gradient(135deg, #3b82f6, #2563eb)"
        )
    elif theme == "light":
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#ffffff", "#1e293b", "#f8fafc", "#fff7ed", "#7c2d12",
            "linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)", "linear-gradient(135deg, #2563eb, #1d4ed8)"
        )
    elif theme == "natal":
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#1a3c34", "#e8f5e9", "#2d5a4b", "#ffebee", "#b71c1c",
            "linear-gradient(135deg, #b71c1c 0%, #d32f2f 100%)", "linear-gradient(135deg, #c62828, #b71c1c)"
        )
    elif theme == "halloween":
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#1a1a2e", "#f0e6d3", "#2e2e4a", "#ffb74d", "#4a1e1e",
            "linear-gradient(135deg, #4a1e1e 0%, #7b2d26 100%)", "linear-gradient(135deg, #e65100, #bf360c)"
        )
    else:
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#0f172a", "#e2e8f0", "#1e293b", "#fef3c7", "#78350f",
            "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)", "linear-gradient(135deg, #3b82f6, #2563eb)"
        )

    if daltonic == "protanopia":
        button_bg = "linear-gradient(135deg, #f4a261, #e76f51)"
    elif daltonic == "deuteranopia":
        button_bg = "linear-gradient(135deg, #2a9d8f, #264653)"
    elif daltonic == "tritanopia":
        button_bg = "linear-gradient(135deg, #9b5de5, #f15bb5)"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background-color: {bg_main}; color: {text_color}; font-size: {font_size}px; }}
    .main-header {{
        background: {header_bg}; padding: 2rem; border-radius: 16px; margin-bottom: 2rem;
        border: 1px solid rgba(0,0,0,0.1); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.3);
    }}
    .main-header h1 {{ color: {text_color}; font-size: 2.5rem; }}
    .explanation-box, .quiz-card, .debate-card {{ background: {card_bg}; border: 1px solid #334155; border-radius: 16px; padding: 2rem; margin: 1.5rem 0; }}
    .primata-box {{
        background: {primata_bg}; border: 2px solid #f59e0b; border-radius: 20px; padding: 2rem; margin: 1.5rem 0;
        color: {primata_text}; position: relative;
    }}
    .primata-box::before {{ content: "🐵"; font-size: 3rem; position: absolute; top: -20px; left: 20px; }}
    .quiz-card:hover {{ transform: translateY(-2px); box-shadow: 0 8px 30px rgba(0,0,0,0.5); }}
    div.stButton>button {{ border-radius: 10px; font-weight: 600; padding: 0.6rem 2rem; border: none; background: {button_bg}; color: white; }}
    .feedback-correct {{ background: rgba(34,197,94,0.1); border-left: 4px solid #22c55e; padding: 1rem; border-radius: 8px; margin: 1rem 0; color: #bbf7d0; }}
    .feedback-incorrect {{ background: rgba(239,68,68,0.1); border-left: 4px solid #ef4444; padding: 1rem; border-radius: 8px; margin: 1rem 0; color: #fecaca; }}
    </style>
    """, unsafe_allow_html=True)

# ---------- Estados da sessão ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# ---------- Tela de login ----------
def tela_login():
    st.markdown('<div class="main-header"><h1>🧠 UltraLearn IA</h1><p>A plataforma definitiva de aprendizado!</p></div>', unsafe_allow_html=True)
    st.subheader("🔐 Faça login ou cadastre-se")

    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        user = st.text_input("Usuário", key="login_user")
        senha = st.text_input("Senha", type="password", key="login_pass")
        if st.button("Entrar"):
            if not user or not senha:
                st.warning("Preencha todos os campos.")
            elif login_usuario(user, senha):
                st.session_state.logged_in = True
                st.session_state.user_id = user
                st.success(f"Bem-vindo, {user}!")
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")

    with tab2:
        new_user = st.text_input("Escolha um nome de usuário", key="cad_user")
        new_pass = st.text_input("Crie uma senha", type="password", key="cad_pass")
        confirm_pass = st.text_input("Confirme a senha", type="password", key="cad_confirm")
        avatar = st.selectbox("Avatar", ["🧑","👩","👨","🐵","🦊","🐱","🐶","👽"], key="cad_avatar")
        if st.button("Cadastrar"):
            if not new_user or not new_pass:
                st.warning("Preencha todos os campos.")
            elif new_pass != confirm_pass:
                st.error("As senhas não coincidem.")
            elif user_exists(new_user):
                st.error("Este nome de usuário já existe.")
            else:
                if criar_usuario(new_user, new_pass, avatar):
                    st.success("Conta criada com sucesso! Faça login.")
                else:
                    st.error("Erro ao criar conta.")

# ---------- Inicialização (apenas após login) ----------
if not st.session_state.logged_in:
    inject_css("dark", 16)
    tela_login()
    st.stop()

# Usuário logado
USER_ID = st.session_state.user_id

# Configurar cliente Groq
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ---------- Funções de persistência ----------
def load_user_data():
    row = conn.execute("SELECT * FROM user_data WHERE user_id = ?", (USER_ID,)).fetchone()
    if row:
        # Garante compatibilidade com tabelas que podem não ter todas as colunas
        colunas = [desc[0] for desc in conn.description]
        data_dict = {
            "user_id": row[0],
            "xp": row[1] if len(row) > 1 else 0,
            "streak": row[2] if len(row) > 2 else 0,
            "last_daily": row[3] if len(row) > 3 else None,
            "achievements": json.loads(row[4]) if len(row) > 4 and row[4] else [],
            "titulos": json.loads(row[5]) if len(row) > 5 and row[5] else []
        }
        return data_dict
    else:
        default = {"user_id": USER_ID, "xp": 0, "streak": 0, "last_daily": None,
                   "achievements": [], "titulos": []}
        conn.execute("INSERT INTO user_data(user_id) VALUES (?)", (USER_ID,))
        conn.commit()
        return default

def save_user_data(updates):
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values())
    conn.execute(f"UPDATE user_data SET {sets} WHERE user_id = ?", (*vals, USER_ID))
    conn.commit()

def add_xp(amount):
    data = load_user_data()
    new_xp = data["xp"] + amount
    today = date.today().isoformat()
    conn.execute("INSERT INTO xp_log (user_id, date, xp_gained) VALUES (?, ?, ?)", (USER_ID, today, amount))
    conn.commit()
    save_user_data({"xp": new_xp})
    achievements = data["achievements"]
    if new_xp >= 100 and "Centenário" not in achievements:
        achievements.append("Centenário"); save_user_data({"achievements": json.dumps(achievements)}); st.balloons()
    if new_xp >= 500 and "Quinhentão" not in achievements:
        achievements.append("Quinhentão"); save_user_data({"achievements": json.dumps(achievements)}); st.balloons()
    if len(achievements) >= 5 and "Colecionador" not in achievements:
        achievements.append("Colecionador"); save_user_data({"achievements": json.dumps(achievements)})
    titulos = data["titulos"]
    if new_xp >= 1000 and "Mestre Supremo" not in titulos:
        titulos.append("Mestre Supremo"); save_user_data({"titulos": json.dumps(titulos)})
    if data["streak"] >= 7 and "Estudante de Férias" not in titulos:
        titulos.append("Estudante de Férias"); save_user_data({"titulos": json.dumps(titulos)})

def update_daily_streak():
    data = load_user_data()
    today = date.today().isoformat()
    if data["last_daily"] != today:
        new_streak = data["streak"] + 1 if data["last_daily"] == (date.today() - timedelta(days=1)).isoformat() else 1
        save_user_data({"streak": new_streak, "last_daily": today})
        if new_streak == 7 and "7 Dias" not in data["achievements"]:
            data["achievements"].append("7 Dias"); save_user_data({"achievements": json.dumps(data["achievements"])})
        return new_streak
    return data["streak"]

def load_questions():
    rows = conn.execute("SELECT * FROM questions WHERE user_id = ?", (USER_ID,)).fetchall()
    questions = []
    for r in rows:
        questions.append({
            "id": r[0], "question": r[2], "type": r[3],
            "options": json.loads(r[4]) if r[4] else [],
            "correct_answer": r[5], "explanation": r[6] or "",
            "interval": r[7], "ease_factor": r[8], "next_review": r[9]
        })
    return questions

def save_question(q):
    conn.execute(
        "INSERT INTO questions(user_id, question, type, options, correct_answer, explanation) VALUES (?,?,?,?,?,?)",
        (USER_ID, q["question"], q["type"], json.dumps(q.get("options", [])), q["correct_answer"], q.get("explanation", ""))
    )
    conn.commit()

def update_spaced_repetition(question, quality):
    now = datetime.now()
    existing = conn.execute(
        "SELECT id, interval, ease_factor FROM questions WHERE question = ? AND user_id = ?",
        (question["question"], USER_ID)
    ).fetchone()
    if existing:
        interval, ease = existing[1], existing[2]
        if quality >= 3:
            interval = int(interval * ease)
            ease += 0.1
        else:
            interval = 1
            ease = max(1.3, ease - 0.2)
        next_review = (now + timedelta(days=interval)).strftime("%Y-%m-%d")
        conn.execute("UPDATE questions SET interval = ?, ease_factor = ?, next_review = ? WHERE id = ?",
                     (interval, ease, next_review, existing[0]))
    else:
        next_review = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO questions(user_id, question, type, options, correct_answer, explanation, interval, ease_factor, next_review) VALUES (?,?,?,?,?,?,1,2.5,?)",
            (USER_ID, question["question"], question["type"], json.dumps(question.get("options", [])),
             question["correct_answer"], question.get("explanation", ""), next_review)
        )
    conn.commit()

# ---------- Funções IA ----------
def gen_explanation(topic):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Explique '{topic}' em português, 3 parágrafos detalhados."}], temperature=0.7, max_tokens=1500)
    return resp.choices[0].message.content.strip()

def gen_resumo(text):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Resuma o seguinte texto em português, de forma concisa (máximo 1 parágrafo): {text}"}], temperature=0.5, max_tokens=500)
    return resp.choices[0].message.content.strip()

def gen_primata(topic, style="normal"):
    prompts = {
        "normal": f"Macaco professor explica '{topic}' em português, aula completa e divertida, 5+ parágrafos.",
        "rapper": f"Macaco rapper explica '{topic}' em forma de rap rimado em português.",
        "conspiracy": f"Macaco conspirador explica '{topic}' como teoria da conspiração maluca.",
        "shakespeare": f"Macaco shakesperiano explica '{topic}' em português arcaico.",
        "standup": f"Macaco comediante faz stand-up sobre '{topic}', com piadas e humor.",
        "eli5": f"Explique '{topic}' como se eu fosse uma criança de 5 anos, de forma super simples.",
        "poesia": f"Macaco poeta explica '{topic}' em forma de poesia rimada."
    }
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompts.get(style, prompts["normal"])}], temperature=0.9, max_tokens=2500)
    return resp.choices[0].message.content.strip()

def gen_quiz(text, difficulty, num):
    dmap = {"fácil":"fácil","médio":"médio","difícil":"difícil"}
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Crie {num} perguntas em português ({dmap[difficulty]}) sobre: {text}. JSON com 'questions'."}], temperature=0.7, max_tokens=2000)
    cont = resp.choices[0].message.content.strip()
    if cont.startswith("```"): cont = cont[cont.find("\n"):].rstrip("```").strip()
    try: return json.loads(cont).get("questions", [])
    except: return []

def gen_redacao_avaliacao(texto):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Avalie esta redação em português: '{texto}'. Dê nota de 0 a 10 e sugira melhorias."}], temperature=0.5, max_tokens=300)
    return resp.choices[0].message.content.strip()

def gen_debate(topic):
    prompt = f"Gere um debate entre dois especialistas (Prós e Contras) sobre '{topic}'. Cada um fala 2 parágrafos. Formato: '**Prós:** ... **Contras:** ...'"
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.8, max_tokens=500)
    return resp.choices[0].message.content.strip()

def gen_historia_interativa(topic, context=None):
    if context is None:
        prompt = f"Inicie uma história interativa em português sobre '{topic}'. Apresente o cenário e dê 3 opções (A, B, C)."
    else:
        prompt = f"Continue a história sobre '{topic}' baseado na escolha {context}. Avance e dê 3 novas opções (A, B, C)."
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.9, max_tokens=600)
    return resp.choices[0].message.content.strip()

def gen_mapa_mental(topic):
    prompt = f"Crie um mapa mental JSON com 'nodes' (conceitos) e 'edges' (pares [origem,destino]) sobre '{topic}'. Apenas JSON."
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.7, max_tokens=500)
    cont = resp.choices[0].message.content.strip()
    if cont.startswith("```"): cont = cont[cont.find("\n"):].rstrip("```").strip()
    try: return json.loads(cont)
    except: return None

def gen_musica(topic):
    prompt = f"Crie uma letra de música em português sobre '{topic}', com refrão e duas estrofes."
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.9, max_tokens=500)
    return resp.choices[0].message.content.strip()

# ---------- Componentes visuais ----------
def show_quiz(questions):
    idx = st.session_state.quiz_index
    total = len(questions)
    if idx >= total:
        st.balloons()
        st.success(f"Quiz concluído! Acertos: {st.session_state.quiz_score}/{total}")
        add_xp(st.session_state.quiz_score * 10)
        if st.button("Limpar Quiz"): st.session_state.quiz_questions=[]; st.session_state.quiz_index=0; st.rerun()
        if st.button("Gerar Flashcards"): st.session_state.flashcards = [(q["question"], q["correct_answer"] + " - " + q.get("explanation","")) for q in questions]; st.rerun()
        if st.button("Exportar PDF"):
            b64 = base64.b64encode(export_quiz_pdf(questions)).decode()
            st.markdown(f'<a href="data:application/octet-stream;base64,{b64}" download="quiz.pdf">Baixar PDF</a>', unsafe_allow_html=True)
        return
    q = questions[idx]
    st.progress(idx/total); st.caption(f"Questão {idx+1}/{total}")
    with st.container():
        st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
        st.subheader(q['question'])
        if q["type"] == "multiple_choice":
            opt = st.radio("Opções", q['options'], index=None)
            if st.button("Responder") and opt:
                user = opt.split('.')[0].strip()
                correct = q['correct_answer']
                if user == correct: st.session_state.quiz_score += 1; st.session_state.quiz_feedback = (True, correct, q['explanation'])
                else: st.session_state.quiz_feedback = (False, correct, q['explanation'])
                st.session_state.quiz_index += 1; st.rerun()
        else:
            opt = st.radio("V/F", ["Verdadeiro","Falso"], index=None)
            if st.button("Responder") and opt:
                user = "Verdadeiro" if opt == "Verdadeiro" else "Falso"
                correct = q['correct_answer']
                if user == correct: st.session_state.quiz_score += 1; st.session_state.quiz_feedback = (True, correct, q['explanation'])
                else: st.session_state.quiz_feedback = (False, correct, q['explanation'])
                st.session_state.quiz_index += 1; st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    if st.session_state.quiz_feedback:
        a,c,e = st.session_state.quiz_feedback
        st.markdown(f'<div class="feedback-{"correct" if a else "incorrect"}">{"✅" if a else "❌"} {e}</div>', unsafe_allow_html=True)
        st.session_state.quiz_feedback=None

def export_quiz_pdf(questions):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for i, q in enumerate(questions):
        pdf.multi_cell(0, 10, f"Q{i+1}: {q['question']}")
        if q["type"] == "multiple_choice":
            for opt in q["options"]: pdf.cell(0, 10, opt, ln=True)
        else: pdf.cell(0, 10, "Verdadeiro ou Falso", ln=True)
        pdf.cell(0, 10, f"Resposta: {q['correct_answer']}", ln=True); pdf.ln(5)
    return pdf.output(dest="S").encode("latin-1")

def text_to_speech(text):
    tts = gTTS(text, lang='pt')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

# ---------- Interface principal (após login) ----------
def main_app():
    # Inicializar estados da sessão
    session_defaults = {
        "explanation": "", "topic": "", "primata_explanation": "",
        "quiz_questions": [], "quiz_index": 0, "quiz_score": 0,
        "quiz_active": False, "quiz_feedback": None,
        "flashcards": [], "theme": "dark", "pomodoro_seconds": 0,
        "pomodoro_active": False, "font_size": 16, "daltonic": None,
        "story_state": None
    }
    for k, v in session_defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    # Sidebar
    with st.sidebar:
        st.markdown("## 👤 Meu Perfil")
        user_row = conn.execute("SELECT avatar, bio FROM users WHERE user_id = ?", (USER_ID,)).fetchone()
        avatar, bio = user_row if user_row else ("🧑", "")
        st.markdown(f"### {avatar} {USER_ID}")
        st.write(bio)
        if st.button("Sair"):
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.rerun()

        st.markdown("---")
        st.markdown("## ⚙️ Aparência")
        theme = st.selectbox("Tema", ["dark","light","natal","halloween"], index=0)
        font_size = st.slider("Fonte", 12, 24, st.session_state.font_size)
        daltonic = st.selectbox("Daltonismo", [None, "protanopia","deuteranopia","tritanopia"])
        inject_css(theme, font_size, daltonic)

        st.markdown("---")
        st.markdown("### ⏱️ Pomodoro")
        if st.button("Iniciar 25 min"): st.session_state.pomodoro_seconds = 25*60; st.session_state.pomodoro_active = True
        if st.session_state.pomodoro_active and st.session_state.pomodoro_seconds > 0:
            st.session_state.pomodoro_seconds -= 1
            mins, secs = divmod(st.session_state.pomodoro_seconds, 60)
            st.metric("⏳ Pomodoro", f"{mins:02d}:{secs:02d}")
        elif st.session_state.pomodoro_active:
            st.sidebar.success("Pomodoro concluído!"); st.session_state.pomodoro_active = False

        st.markdown("---")
        data = load_user_data()
        st.metric("XP Total", data["xp"])
        st.metric("Streak", f"{data['streak']} dias")
        st.write("🏅 Títulos:", ", ".join(data["titulos"]) if data["titulos"] else "Nenhum")

    st.markdown('<div class="main-header"><h1>🧠 UltraLearn IA Titanium</h1><p>A plataforma definitiva de aprendizado!</p></div>', unsafe_allow_html=True)

    tabs = st.tabs([
        "📖 Estudar", "🎓 Aula Completa", "🧠 Quiz", "🐵 Primata",
        "🗺️ Mapa Mental", "⚖️ Debate", "📖 História", "🎵 Música",
        "✍️ Redação", "👨‍🏫 Professor", "📊 Progresso", "📅 Diário"
    ])

    # As abas seguem exatamente como já estavam no código anterior (mantive todas as funcionalidades)
    # Reproduzo aqui as abas 0 a 11, mas sem alterações.

    # Aba Estudar
    with tabs[0]:
        st.subheader("Modo de Estudo")
        uploaded_pdf = st.file_uploader("Envie um PDF", type="pdf")
        if uploaded_pdf:
            reader = PyPDF2.PdfReader(uploaded_pdf)
            text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
            st.text_area("Texto extraído", text, height=100)
            if st.button("Gerar Explicação do PDF") and text:
                st.session_state.explanation = gen_explanation(text[:3000]); st.rerun()
        uploaded_img = st.file_uploader("Ou envie uma imagem com texto", type=["png","jpg","jpeg"])
        if uploaded_img:
            img = Image.open(uploaded_img)
            extracted = pytesseract.image_to_string(img, lang='por')
            st.text_area("Texto extraído", extracted, height=100)
            if st.button("Gerar Explicação da Imagem") and extracted:
                st.session_state.explanation = gen_explanation(extracted[:2000]); st.rerun()
        wiki_query = st.text_input("Pesquisar na Wikipedia:")
        if wiki_query and st.button("Buscar"):
            try:
                wiki_text = wikipedia.summary(wiki_query, sentences=10)
                st.session_state.explanation = wiki_text; st.rerun()
            except: st.error("Tópico não encontrado.")
        topic = st.text_input("Ou digite um assunto:", key="topic")
        if st.button("Gerar Explicação") and topic:
            st.session_state.explanation = gen_explanation(topic); add_xp(5); st.rerun()
        if st.session_state.explanation:
            st.markdown(f'<div class="explanation-box">{st.session_state.explanation}</div>', unsafe_allow_html=True)
            if st.button("🔊 Ouvir"): st.audio(text_to_speech(st.session_state.explanation), format='audio/mp3')
            if st.button("Gerar Resumão"):
                st.markdown(f"**Resumo:** {gen_resumo(st.session_state.explanation)}")
            d = st.selectbox("Dificuldade", ["Fácil","Médio","Difícil"], index=1)
            n = st.number_input("Perguntas", 1,20,5)
            if st.button("Criar Quiz"):
                st.session_state.quiz_questions = gen_quiz(st.session_state.explanation, d, n)
                st.session_state.quiz_index = 0; st.session_state.quiz_active = True; st.rerun()

    # Aba Aula Completa
    with tabs[1]:
        st.subheader("🎓 Aula Completa")
        top_aula = st.text_input("Tópico:", key="aula_topic")
        if st.button("Iniciar Aula Completa") and top_aula:
            exp = gen_explanation(top_aula); st.markdown(exp); add_xp(5)
            quiz = gen_quiz(exp, "médio", 5)
            if quiz:
                st.session_state.quiz_questions = quiz; st.session_state.quiz_index = 0; st.session_state.quiz_score = 0; st.session_state.quiz_active = True; st.rerun()
        if st.session_state.quiz_active and st.session_state.quiz_questions:
            show_quiz(st.session_state.quiz_questions)

    # Aba Quiz
    with tabs[2]:
        st.subheader("🧠 Modos de Quiz")
        quiz_mode = st.radio("Escolha:", ["Normal", "Caótico (V/F)", "Maratona de Revisão"])
        if quiz_mode == "Normal":
            if st.session_state.quiz_active and st.session_state.quiz_questions:
                show_quiz(st.session_state.quiz_questions)
            else: st.info("Crie um quiz primeiro.")
        elif quiz_mode == "Caótico (V/F)":
            if "caotico_questions" not in st.session_state: st.session_state.caotico_questions = []
            top_caos = st.text_input("Tópico para quiz caótico:")
            if st.button("Gerar Quiz Caótico") and top_caos:
                prompt = f"Crie 10 afirmações sobre '{top_caos}', metade verdadeiras e metade falsas. JSON com 'questions' (array de objetos com 'afirmacao' e 'verdadeiro' booleano)."
                resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
                    messages=[{"role":"user","content": prompt}], temperature=0.9, max_tokens=1000)
                cont = resp.choices[0].message.content.strip()
                if cont.startswith("```"): cont = cont[cont.find("\n"):].rstrip("```").strip()
                try:
                    caos = json.loads(cont).get("questions", [])
                    st.session_state.caotico_questions = caos; st.session_state.caos_idx = 0; st.session_state.caos_score = 0
                except: st.error("Erro ao gerar.")
            if st.session_state.caotico_questions:
                idx = st.session_state.caos_idx
                if idx < len(st.session_state.caotico_questions):
                    q = st.session_state.caotico_questions[idx]
                    st.write(q['afirmacao'])
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("✅ Verdadeiro"):
                            if q['verdadeiro']: st.session_state.caos_score += 1; st.success("Correto!")
                            else: st.error("Falso!")
                            st.session_state.caos_idx += 1; st.rerun()
                    with col2:
                        if st.button("❌ Falso"):
                            if not q['verdadeiro']: st.session_state.caos_score += 1; st.success("Correto!")
                            else: st.error("Verdadeiro!")
                            st.session_state.caos_idx += 1; st.rerun()
                else:
                    st.success(f"Fim! Acertos: {st.session_state.caos_score}/{len(st.session_state.caotico_questions)}")
        else:
            due = [q for q in load_questions() if q.get("next_review") and q["next_review"] <= date.today().isoformat()]
            if due:
                if st.button(f"Revisar {len(due)} questões"):
                    st.session_state.quiz_questions = due; st.session_state.quiz_index = 0; st.session_state.quiz_score = 0; st.session_state.quiz_active = True; st.rerun()
                if st.session_state.quiz_active and st.session_state.quiz_questions:
                    show_quiz(st.session_state.quiz_questions)
            else: st.success("Nenhuma revisão pendente!")

    # Aba Primata
    with tabs[3]:
        estilos = ["Normal","Rapper","Conspiração","Shakespeare","Stand-Up","ELI5","Poesia"]
        estilo = st.selectbox("Estilo do Macaco:", estilos)
        pt = st.text_input("Tópico primata:", key="ptopic")
        if st.button("Macaco Sábio") and pt:
            chave = estilo.lower().replace("-","")
            st.session_state.primata_explanation = gen_primata(pt, chave)
            add_xp(10); st.rerun()
        if st.session_state.primata_explanation:
            st.markdown(f'<div class="primata-box">{st.session_state.primata_explanation}</div>', unsafe_allow_html=True)

    # Aba Mapa Mental
    with tabs[4]:
        st.subheader("🗺️ Mapa Mental")
        mapa_topic = st.text_input("Tópico:", key="mapa")
        if st.button("Gerar Mapa") and mapa_topic:
            data = gen_mapa_mental(mapa_topic)
            if data:
                g = graphviz.Digraph()
                for node in data.get("nodes", []): g.node(node)
                for edge in data.get("edges", []):
                    if len(edge) == 2: g.edge(edge[0], edge[1])
                st.graphviz_chart(g)
            else: st.error("Não foi possível gerar o mapa mental.")

    # Aba Debate
    with tabs[5]:
        st.subheader("⚖️ Debate de Especialistas")
        debate_topic = st.text_input("Tópico do debate:", key="debate")
        if st.button("Iniciar Debate") and debate_topic:
            debate_text = gen_debate(debate_topic)
            st.markdown(debate_text)
            col1, col2, col3 = st.columns([1,1,1])
            with col1:
                if st.button("👍 Prós"): st.success("Você votou nos Prós!")
            with col2:
                if st.button("👎 Contras"): st.success("Você votou nos Contras!")
            with col3:
                if st.button("🤝 Empate"): st.success("Você considerou empate!")

    # Aba História Interativa
    with tabs[6]:
        st.subheader("📖 História Interativa (RPG)")
        hist_topic = st.text_input("Tema da história:", key="hist")
        if st.button("Começar História") and hist_topic:
            st.session_state.story_state = None
            hist_text = gen_historia_interativa(hist_topic)
            st.session_state.story_state = {"text": hist_text, "topic": hist_topic}
            st.rerun()
        if st.session_state.story_state:
            st.write(st.session_state.story_state["text"])
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("Opção A"):
                    st.session_state.story_state["text"] = gen_historia_interativa(st.session_state.story_state["topic"], "A")
                    st.rerun()
            with col2:
                if st.button("Opção B"):
                    st.session_state.story_state["text"] = gen_historia_interativa(st.session_state.story_state["topic"], "B")
                    st.rerun()
            with col3:
                if st.button("Opção C"):
                    st.session_state.story_state["text"] = gen_historia_interativa(st.session_state.story_state["topic"], "C")
                    st.rerun()
            if st.button("Reiniciar História"):
                st.session_state.story_state = None; st.rerun()

    # Aba Música
    with tabs[7]:
        st.subheader("🎵 Gerador de Música de Estudo")
        musica_topic = st.text_input("Tópico da música:", key="musica")
        if st.button("Compor Letra") and musica_topic:
            letra = gen_musica(musica_topic)
            st.markdown(f"**Letra:**\n{letra}")
            st.audio("https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3", format="audio/mp3")

    # Aba Redação
    with tabs[8]:
        st.subheader("✍️ Redação Assistida")
        redacao = st.text_area("Escreva sua redação:", height=200)
        if st.button("Avaliar Redação") and redacao:
            avaliacao = gen_redacao_avaliacao(redacao)
            st.markdown(f"### Avaliação da IA:\n{avaliacao}")
            add_xp(15)

    # Aba Professor vs Aluno
    with tabs[9]:
        st.subheader("👨‍🏫 Professor vs Aluno")
        ptopic_prof = st.text_input("Tópico para aula:", key="prof_topic")
        if "prof_questions" not in st.session_state: st.session_state.prof_questions = []
        if st.button("Iniciar Aula") and ptopic_prof:
            exp = gen_explanation(ptopic_prof)
            st.session_state.prof_questions = gen_quiz(exp, "médio", 5)
            st.session_state.prof_idx = 0
        if st.session_state.prof_questions:
            idx = st.session_state.prof_idx
            if idx < len(st.session_state.prof_questions):
                q = st.session_state.prof_questions[idx]
                st.write(q['question'])
                ans = st.text_input("Sua resposta:", key=f"prof_ans_{idx}")
                if st.button("Enviar Resposta"):
                    if ans.strip().lower() == q['correct_answer'].lower(): st.success("Correto!"); add_xp(5)
                    else: st.error(f"Errado. Resposta: {q['correct_answer']}"); st.info(q['explanation'])
                    st.session_state.prof_idx += 1; st.rerun()
            else: st.success("Aula concluída!")

    # Aba Progresso
    with tabs[10]:
        st.subheader("📊 Seu Progresso")
        data = load_user_data()
        col1, col2, col3 = st.columns(3)
        col1.metric("XP", data["xp"])
        col2.metric("Streak", data["streak"])
        col3.metric("Títulos", len(data["titulos"]))
        st.write("🏆 Conquistas:", ", ".join(data["achievements"]) if data["achievements"] else "Nenhuma")

        logs = conn.execute("SELECT date, SUM(xp_gained) FROM xp_log WHERE user_id=? GROUP BY date ORDER BY date", (USER_ID,)).fetchall()
        if logs:
            df = pd.DataFrame(logs, columns=["Data", "XP ganho"])
            df['Data'] = pd.to_datetime(df['Data'])
            st.line_chart(df.set_index("Data"))
            fig = px.density_heatmap(df, x="Data", y="XP ganho", title="Atividade Diária")
            st.plotly_chart(fig)

        ranking = conn.execute("""
            SELECT user_id, SUM(xp_gained) as total_xp
            FROM xp_log
            WHERE date >= date('now','-7 days')
            GROUP BY user_id ORDER BY total_xp DESC LIMIT 10
        """).fetchall()
        if ranking:
            st.subheader("🏅 Ranking Semanal (Top 10)")
            df_rank = pd.DataFrame(ranking, columns=["Usuário", "XP na Semana"])
            st.table(df_rank)

        top_topics = conn.execute("SELECT topic, SUM(quizzes) as total_quizzes, SUM(errors) as total_errors FROM topics WHERE user_id=? GROUP BY topic", (USER_ID,)).fetchall()
        if top_topics:
            st.subheader("📚 Tópicos Estudados")
            df_top = pd.DataFrame(top_topics, columns=["Tópico", "Quizzes", "Erros"])
            df_top["Taxa de Erro"] = df_top["Erros"] / df_top["Quizzes"] * 100
            st.dataframe(df_top)

    # Aba Diário
    with tabs[11]:
        st.subheader("📅 Desafio Diário")
        data = load_user_data()
        today = date.today().isoformat()
        if data["last_daily"] != today:
            daily_topic = random.choice(["Inteligência Artificial", "História do Brasil", "Sistema Solar", "Mitologia Grega"])
            st.markdown(f"### Tópico do dia: **{daily_topic}**")
            if st.button("Gerar Quiz do Dia"):
                exp = gen_explanation(daily_topic)
                st.session_state.daily_questions = gen_quiz(exp, "médio", 3)
                st.session_state.daily_idx = 0; st.rerun()
        else:
            st.success(f"Desafio de hoje já concluído! Streak: {data['streak']} dias")
        if "daily_questions" in st.session_state and st.session_state.daily_questions:
            idx = st.session_state.daily_idx
            if idx < len(st.session_state.daily_questions):
                q = st.session_state.daily_questions[idx]
                st.write(q['question'])
                ans = st.radio("Opções" if q["type"]=="multiple_choice" else "V/F",
                               q['options'] if q["type"]=="multiple_choice" else ["Verdadeiro","Falso"],
                               index=None, key=f"daily_{idx}")
                if st.button("Responder Diário") and ans:
                    user = ans.split('.')[0].strip() if q["type"]=="multiple_choice" else ("Verdadeiro" if ans=="Verdadeiro" else "Falso")
                    if user == q['correct_answer']:
                        st.success("Correto!"); add_xp(20)
                    else:
                        st.error(f"Errado. Resposta: {q['correct_answer']}")
                    st.session_state.daily_idx += 1
                    if st.session_state.daily_idx >= len(st.session_state.daily_questions):
                        update_daily_streak()
                        st.balloons()
                        st.success("Desafio diário concluído! +20 XP")
                    st.rerun()

# ---------- Execução final ----------
if __name__ == "__main__":
    if st.session_state.logged_in:
        main_app()
    else:
        inject_css("dark", 16)
        tela_login()