#!/usr/bin/env python3
"""
UltraLearn IA – Premium Edition (Visual incrível + todas as funcionalidades)
"""
import streamlit as st
import json, os, random, io, base64, hashlib, uuid
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
from streamlit_cookies_manager import CookieManager

# ---------- Configuração da página ----------
st.set_page_config(page_title="UltraLearn IA", page_icon="🧠", layout="centered")

# ---------- Cookies ----------
cookies = CookieManager()
if not cookies.ready():
    st.stop()

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

conn.execute("""
    CREATE TABLE IF NOT EXISTS auth_tokens (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires TEXT NOT NULL
    )
""")

# Migração: adiciona coluna 'titulos' se não existir
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN titulos TEXT DEFAULT '[]'")
    conn.commit()
except:
    pass

conn.commit()

# ---------- Funções de autenticação ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def criar_usuario(user_id, password, avatar="🧑", bio=""):
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
    row = conn.execute("SELECT password_hash FROM users WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return False
    return row[0] == hash_password(password)

def user_exists(user_id):
    return conn.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)).fetchone() is not None

def gerar_token(user_id):
    token = str(uuid.uuid4())
    expires = (datetime.now() + timedelta(days=30)).isoformat()
    conn.execute("INSERT INTO auth_tokens (token, user_id, expires) VALUES (?, ?, ?)", (token, user_id, expires))
    conn.commit()
    return token

def validar_token(token):
    row = conn.execute("SELECT user_id, expires FROM auth_tokens WHERE token = ?", (token,)).fetchone()
    if not row:
        return None
    user_id, expires = row
    if datetime.fromisoformat(expires) < datetime.now():
        conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
        conn.commit()
        return None
    return user_id

def remover_token(token):
    conn.execute("DELETE FROM auth_tokens WHERE token = ?", (token,))
    conn.commit()

# ---------- CSS Mega Premium (11 temas) ----------
def inject_css(theme="dark", font_size=16, daltonic=None):
    themes = {
        "dark": {
            "bg_main": "#0f172a", "text_color": "#e2e8f0", "card_bg": "rgba(30,41,59,0.8)",
            "primata_bg": "#fef3c7", "primata_text": "#78350f",
            "header_bg": "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
            "button_bg": "linear-gradient(135deg, #3b82f6, #2563eb)", "accent": "#3b82f6"
        },
        "light": {
            "bg_main": "#ffffff", "text_color": "#1e293b", "card_bg": "rgba(248,250,252,0.9)",
            "primata_bg": "#fff7ed", "primata_text": "#7c2d12",
            "header_bg": "linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)",
            "button_bg": "linear-gradient(135deg, #2563eb, #1d4ed8)", "accent": "#2563eb"
        },
        "ocean": {
            "bg_main": "#0c4a6e", "text_color": "#e0f2fe", "card_bg": "rgba(12,74,110,0.8)",
            "primata_bg": "#d1fae5", "primata_text": "#065f46",
            "header_bg": "linear-gradient(135deg, #0891b2 0%, #0c4a6e 100%)",
            "button_bg": "linear-gradient(135deg, #22d3ee, #0891b2)", "accent": "#22d3ee"
        },
        "sunset": {
            "bg_main": "#4a1942", "text_color": "#ffe4e6", "card_bg": "rgba(74,25,66,0.8)",
            "primata_bg": "#fff0f3", "primata_text": "#9d174d",
            "header_bg": "linear-gradient(135deg, #be185d 0%, #4a1942 100%)",
            "button_bg": "linear-gradient(135deg, #fb7185, #e11d48)", "accent": "#fb7185"
        },
        "forest": {
            "bg_main": "#1a2e1a", "text_color": "#d1fae5", "card_bg": "rgba(26,46,26,0.8)",
            "primata_bg": "#f0fff0", "primata_text": "#14532d",
            "header_bg": "linear-gradient(135deg, #2d6a4f 0%, #1a2e1a 100%)",
            "button_bg": "linear-gradient(135deg, #4ade80, #16a34a)", "accent": "#4ade80"
        },
        "neon": {
            "bg_main": "#0a0a0a", "text_color": "#f0f0f0", "card_bg": "rgba(10,10,10,0.9)",
            "primata_bg": "#f0f0f0", "primata_text": "#ff007f",
            "header_bg": "linear-gradient(135deg, #ff007f 0%, #0a0a0a 100%)",
            "button_bg": "linear-gradient(135deg, #ff007f, #7f00ff)", "accent": "#ff007f"
        },
        "marshmallow": {
            "bg_main": "#fdf2f8", "text_color": "#4a1942", "card_bg": "rgba(255,255,255,0.9)",
            "primata_bg": "#fce7f3", "primata_text": "#9d174d",
            "header_bg": "linear-gradient(135deg, #fbcfe8 0%, #fce7f3 100%)",
            "button_bg": "linear-gradient(135deg, #f472b6, #db2777)", "accent": "#f472b6"
        },
        "midnight": {
            "bg_main": "#0b0f19", "text_color": "#cbd5e1", "card_bg": "rgba(15,23,42,0.9)",
            "primata_bg": "#1e293b", "primata_text": "#38bdf8",
            "header_bg": "linear-gradient(135deg, #1e293b 0%, #0b0f19 100%)",
            "button_bg": "linear-gradient(135deg, #38bdf8, #0284c7)", "accent": "#38bdf8"
        },
        "aurora": {
            "bg_main": "#2e1065", "text_color": "#ede9fe", "card_bg": "rgba(46,16,101,0.8)",
            "primata_bg": "#f5f3ff", "primata_text": "#4c1d95",
            "header_bg": "linear-gradient(135deg, #8b5cf6 0%, #2e1065 100%)",
            "button_bg": "linear-gradient(135deg, #a78bfa, #7c3aed)", "accent": "#a78bfa"
        },
        "coffee": {
            "bg_main": "#3c2a21", "text_color": "#e6d5c9", "card_bg": "rgba(60,42,33,0.9)",
            "primata_bg": "#f5f0e6", "primata_text": "#5c3a21",
            "header_bg": "linear-gradient(135deg, #5c3a21 0%, #3c2a21 100%)",
            "button_bg": "linear-gradient(135deg, #b8956a, #8b5a2b)", "accent": "#b8956a"
        },
        "cyberpunk": {
            "bg_main": "#0d0221", "text_color": "#ff2a6d", "card_bg": "rgba(13,2,33,0.95)",
            "primata_bg": "#1a0a2e", "primata_text": "#05d9e8",
            "header_bg": "linear-gradient(135deg, #ff2a6d 0%, #0d0221 100%)",
            "button_bg": "linear-gradient(135deg, #05d9e8, #ff2a6d)", "accent": "#05d9e8"
        }
    }

    t = themes.get(theme, themes["dark"])

    # Ajuste para daltonismo
    if daltonic == "protanopia":
        t["button_bg"] = "linear-gradient(135deg, #f4a261, #e76f51)"
        t["accent"] = "#f4a261"
    elif daltonic == "deuteranopia":
        t["button_bg"] = "linear-gradient(135deg, #2a9d8f, #264653)"
        t["accent"] = "#2a9d8f"
    elif daltonic == "tritanopia":
        t["button_bg"] = "linear-gradient(135deg, #9b5de5, #f15bb5)"
        t["accent"] = "#9b5de5"

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Plus+Jakarta+Sans:wght@400;500;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Outfit', 'Plus Jakarta Sans', sans-serif;
        background-color: {t["bg_main"]};
        color: {t["text_color"]};
        font-size: {font_size}px;
    }}

    /* Cabeçalho principal */
    .main-header {{
        background: {t["header_bg"]};
        padding: 2.5rem 2rem;
        border-radius: 32px;
        margin-bottom: 2rem;
        border: 1px solid rgba(255,255,255,0.08);
        box-shadow: 0 20px 40px -20px rgba(0,0,0,0.4);
        backdrop-filter: blur(20px);
        position: relative;
        overflow: hidden;
    }}
    .main-header::before {{
        content: "";
        position: absolute;
        top: -50%;
        left: -50%;
        width: 200%;
        height: 200%;
        background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%);
        animation: rotate 20s linear infinite;
    }}
    @keyframes rotate {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}

    /* Cartões com glassmorphism */
    .explanation-box, .quiz-card, .debate-card, .primata-box {{
        background: {t["card_bg"]};
        backdrop-filter: blur(15px);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 24px;
        padding: 2rem;
        margin: 1.5rem 0;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        transition: all 0.3s ease;
    }}
    .quiz-card:hover, .explanation-box:hover {{
        transform: translateY(-4px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.5);
    }}

    /* Botões ultra estilizados */
    div.stButton > button {{
        border-radius: 14px;
        font-weight: 600;
        padding: 0.7rem 2.5rem;
        border: none;
        background: {t["button_bg"]};
        color: white;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        font-size: 0.9rem;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        position: relative;
        overflow: hidden;
    }}
    div.stButton > button:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 25px rgba(59,130,246,0.4);
    }}
    div.stButton > button:active {{
        transform: translateY(0);
    }}

    /* Feedback de respostas */
    .feedback-correct {{
        background: rgba(34,197,94,0.15);
        border-left: 4px solid #22c55e;
        padding: 1rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: #bbf7d0;
        backdrop-filter: blur(5px);
    }}
    .feedback-incorrect {{
        background: rgba(239,68,68,0.15);
        border-left: 4px solid #ef4444;
        padding: 1rem;
        border-radius: 12px;
        margin: 1rem 0;
        color: #fecaca;
        backdrop-filter: blur(5px);
    }}

    /* Barra de progresso animada */
    .stProgress > div > div {{
        background: linear-gradient(90deg, {t["accent"]}, {t["text_color"]}) !important;
        border-radius: 10px;
        transition: width 0.5s ease;
    }}

    /* Inputs e textareas */
    textarea, input {{
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 14px !important;
        color: {t["text_color"]} !important;
        padding: 0.8rem 1rem !important;
        backdrop-filter: blur(5px);
    }}

    /* Abas (tabs) estilizadas */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0.5rem;
        background: transparent;
        border-bottom: 2px solid rgba(255,255,255,0.1);
    }}
    .stTabs [data-baseweb="tab"] {{
        color: {t["text_color"]};
        font-weight: 500;
        border-radius: 12px 12px 0 0;
        padding: 0.6rem 1.2rem;
        transition: all 0.2s;
    }}
    .stTabs [aria-selected="true"] {{
        background: {t["accent"]} !important;
        color: white !important;
    }}

    /* Esconder ícones padrão indesejados */
    #MainMenu {{ visibility: hidden; }}
    footer {{ visibility: hidden; }}
    </style>
    """, unsafe_allow_html=True)

# ---------- Verificação de cookie persistente ----------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_id = None

if not st.session_state.logged_in:
    cookie_token = cookies.get("ultralearn_token")
    if cookie_token:
        user_id = validar_token(cookie_token)
        if user_id:
            st.session_state.logged_in = True
            st.session_state.user_id = user_id
            cookies["ultralearn_token"] = cookie_token
            cookies.save()
        else:
            cookies["ultralearn_token"] = ""
            cookies.save()

# ---------- Tela de login ----------
def tela_login():
    LOGO_URL = "https://i.imgur.com/cfSvLdE.png"
    MASCOT_URL = "https://i.imgur.com/dDnr8pn.png"

    col1, col2 = st.columns([1, 2])
    with col1:
        st.image(LOGO_URL, width=250)
    with col2:
        st.markdown("""
        <div style="margin-top: 2rem;">
            <h1 style="font-size: 3.5rem; font-weight: 700; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">UltraLearn IA</h1>
            <p style="font-size: 1.3rem; opacity: 0.8;">A plataforma definitiva de aprendizado</p>
        </div>
        """, unsafe_allow_html=True)

    st.subheader("🔐 Faça login ou cadastre-se")
    tab1, tab2 = st.tabs(["Login", "Cadastro"])

    with tab1:
        user = st.text_input("Usuário", key="login_user")
        senha = st.text_input("Senha", type="password", key="login_pass")
        lembrar = st.checkbox("Lembrar de mim (30 dias)", value=True)
        if st.button("Entrar"):
            if not user or not senha:
                st.warning("Preencha todos os campos.")
            elif login_usuario(user, senha):
                st.session_state.logged_in = True
                st.session_state.user_id = user
                if lembrar:
                    token = gerar_token(user)
                    cookies["ultralearn_token"] = token
                    cookies.save()
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

# ---------- Inicialização ----------
if not st.session_state.logged_in:
    inject_css("dark", 16)
    tela_login()
    st.stop()

USER_ID = st.session_state.user_id
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ---------- Funções de persistência ----------
def load_user_data():
    row = conn.execute("SELECT * FROM user_data WHERE user_id = ?", (USER_ID,)).fetchone()
    if row:
        return {
            "user_id": row[0],
            "xp": row[1] if len(row) > 1 else 0,
            "streak": row[2] if len(row) > 2 else 0,
            "last_daily": row[3] if len(row) > 3 else None,
            "achievements": json.loads(row[4]) if len(row) > 4 and row[4] else [],
            "titulos": json.loads(row[5]) if len(row) > 5 and row[5] else []
        }
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

def gen_continuacao(topic, texto_anterior):
    prompt = f"Com base na explicação anterior sobre '{topic}':\n{texto_anterior}\n\nForneça mais detalhes, curiosidades e aprofundamentos sobre o mesmo tópico. Continue a explicação de forma fluida e aprofundada, sem repetir o que já foi dito."
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.8, max_tokens=2000)
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
    prompt = f"Crie um mapa mental JSON com 'nodes' (array de strings, cada string é um conceito) e 'edges' (array de pares [origem,destino]) sobre '{topic}'. Apenas JSON. Exemplo: {{\"nodes\":[\"Física\",\"Mecânica\"],\"edges\":[[\"Física\",\"Mecânica\"]]}}"
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompt}], temperature=0.7, max_tokens=500)
    cont = resp.choices[0].message.content.strip()
    if cont.startswith("```"): cont = cont[cont.find("\n"):].rstrip("```").strip()
    try:
        data = json.loads(cont)
        nodes = data.get("nodes", [])
        normalized_nodes = []
        for n in nodes:
            if isinstance(n, str):
                normalized_nodes.append(n)
            elif isinstance(n, dict):
                for key in ("name", "label", "id"):
                    if key in n and isinstance(n[key], str):
                        normalized_nodes.append(n[key])
                        break
                else:
                    first_str = next((v for v in n.values() if isinstance(v, str)), None)
                    if first_str:
                        normalized_nodes.append(first_str)
                    else:
                        normalized_nodes.append(str(n))
            else:
                normalized_nodes.append(str(n))
        edges = data.get("edges", [])
        normalized_edges = []
        for e in edges:
            if isinstance(e, list) and len(e) == 2:
                normalized_edges.append([str(e[0]), str(e[1])])
        return {"nodes": normalized_nodes, "edges": normalized_edges}
    except:
        return None

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

# ---------- Interface principal ----------
def main_app():
    # Inicialização expandida de estados da sessão
    session_defaults = {
        "explanation": "", "topic": "", "primata_explanation": "",
        "quiz_questions": [], "quiz_index": 0, "quiz_score": 0,
        "quiz_active": False, "quiz_feedback": None,
        "flashcards": [], "theme": "dark", "pomodoro_seconds": 0,
        "pomodoro_active": False, "font_size": 16, "daltonic": None,
        "story_state": None,
        "prof_questions": [], "prof_idx": 0,
        "daily_questions": [], "daily_idx": 0,
        "caotico_questions": [], "caos_idx": 0, "caos_score": 0
    }
    for k, v in session_defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    with st.sidebar:
        # Logo na sidebar
        LOGO_SIDEBAR_URL = "https://i.imgur.com/cfSvLdE.png"
        if LOGO_SIDEBAR_URL:
            st.image(LOGO_SIDEBAR_URL, width=200)
        else:
            st.markdown("## 🧠 UltraLearn IA")

        st.markdown("---")
        st.markdown("## 👤 Meu Perfil")
        user_row = conn.execute("SELECT avatar, bio FROM users WHERE user_id = ?", (USER_ID,)).fetchone()
        avatar, bio = user_row if user_row else ("🧑", "")
        st.markdown(f"### {avatar} {USER_ID}")
        st.write(bio)
        if st.button("🚪 Sair"):
            cookie_token = cookies.get("ultralearn_token")
            if cookie_token:
                remover_token(cookie_token)
            cookies["ultralearn_token"] = ""
            cookies.save()
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.rerun()

        st.markdown("---")
        st.markdown("## ⚙️ Aparência")
        theme = st.selectbox("Tema", [
            "dark", "light", "ocean", "sunset", "forest", "neon",
            "marshmallow", "midnight", "aurora", "coffee", "cyberpunk"
        ], index=0)
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

        # Ranking lateral
        st.markdown("---")
        st.markdown("## 🏅 Ranking Geral")
        ranking = conn.execute("""
            SELECT u.user_id, COALESCE(SUM(xp.xp_gained), 0) as total_xp
            FROM users u
            LEFT JOIN xp_log xp ON u.user_id = xp.user_id
            GROUP BY u.user_id
            ORDER BY total_xp DESC
        """).fetchall()
        if ranking:
            df_rank = pd.DataFrame(ranking, columns=["Usuário", "XP Total"])
            avatares = {r[0]: (conn.execute("SELECT avatar FROM users WHERE user_id = ?", (r[0],)).fetchone() or ("🧑",))[0] for r in ranking}
            df_rank["Avatar"] = df_rank["Usuário"].map(avatares)
            df_rank = df_rank[["Avatar", "Usuário", "XP Total"]]
            st.dataframe(df_rank, hide_index=True, use_container_width=True)
        else:
            st.write("Nenhum usuário ainda.")

    # Cabeçalho principal
    st.markdown("""
    <div class="main-header">
        <h1>🧠 UltraLearn IA</h1>
        <p>Domine qualquer assunto com inteligência artificial</p>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([
        "📖 Estudar", "🎓 Aula Completa", "🧠 Quiz", "🐵 Primata",
        "🗺️ Mapa Mental", "⚖️ Debate", "📖 História", "🎵 Música",
        "✍️ Redação", "👨‍🏫 Professor", "📊 Progresso", "📅 Diário"
    ])

    # Aba Estudar (com continuação)
    with tabs[0]:
        st.subheader("Modo de Estudo")
        uploaded_pdf = st.file_uploader("Envie um PDF", type="pdf")
        if uploaded_pdf:
            reader = PyPDF2.PdfReader(uploaded_pdf)
            text = " ".join([page.extract_text() for page in reader.pages if page.extract_text()])
            st.text_area("Texto extraído", text, height=100)
            if st.button("Gerar Explicação do PDF") and text:
                st.session_state.explanation = gen_explanation(text[:3000]); st.session_state.topic = "PDF"; st.rerun()
        uploaded_img = st.file_uploader("Ou envie uma imagem com texto", type=["png","jpg","jpeg"])
        if uploaded_img:
            img = Image.open(uploaded_img)
            extracted = pytesseract.image_to_string(img, lang='por')
            st.text_area("Texto extraído", extracted, height=100)
            if st.button("Gerar Explicação da Imagem") and extracted:
                st.session_state.explanation = gen_explanation(extracted[:2000]); st.session_state.topic = "Imagem"; st.rerun()
        wiki_query = st.text_input("Pesquisar na Wikipedia:")
        if wiki_query and st.button("Buscar"):
            try:
                wiki_text = wikipedia.summary(wiki_query, sentences=10)
                st.session_state.explanation = wiki_text; st.session_state.topic = wiki_query; st.rerun()
            except: st.error("Tópico não encontrado.")
        topic = st.text_input("Ou digite um assunto:", key="topic_input")
        if st.button("Gerar Explicação") and topic:
            st.session_state.explanation = gen_explanation(topic); st.session_state.topic = topic; add_xp(5); st.rerun()
        if st.session_state.explanation:
            st.markdown(f'<div class="explanation-box">{st.session_state.explanation}</div>', unsafe_allow_html=True)
            if st.button("🔊 Ouvir"): st.audio(text_to_speech(st.session_state.explanation), format='audio/mp3')
            if st.button("🧠 Quero saber mais"):
                with st.spinner("Aprofundando o conhecimento..."):
                    continuation = gen_continuacao(st.session_state.topic, st.session_state.explanation)
                    st.session_state.explanation += "\n\n" + continuation
                st.rerun()
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
            with st.spinner("Desenhando mapa..."):
                data = gen_mapa_mental(mapa_topic)
                if data and data["nodes"]:
                    g = graphviz.Digraph()
                    for node in data["nodes"]:
                        if isinstance(node, str) and node.strip():
                            g.node(node.strip())
                    for edge in data["edges"]:
                        if len(edge) == 2 and edge[0] and edge[1]:
                            g.edge(str(edge[0]).strip(), str(edge[1]).strip())
                    st.graphviz_chart(g)
                else:
                    st.error("Não foi possível gerar o mapa mental.")

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

    # Aba Professor vs Aluno – CORRIGIDA
    with tabs[9]:
        st.subheader("👨‍🏫 Professor vs Aluno")
        ptopic_prof = st.text_input("Tópico para aula:", key="prof_topic")
        if "prof_questions" not in st.session_state: st.session_state.prof_questions = []
        if "prof_idx" not in st.session_state: st.session_state.prof_idx = 0
        if st.button("Iniciar Aula") and ptopic_prof:
            exp = gen_explanation(ptopic_prof)
            st.session_state.prof_questions = gen_quiz(exp, "médio", 5)
            st.session_state.prof_idx = 0
            st.rerun()
        if st.session_state.prof_questions:
            idx = st.session_state.prof_idx
            if idx < len(st.session_state.prof_questions):
                q = st.session_state.prof_questions[idx]
                st.write(q['question'])
                ans = st.text_input("Sua resposta:", key=f"prof_ans_{idx}")
                if st.button("Enviar Resposta"):
                    if ans.strip().lower() == q['correct_answer'].lower():
                        st.success("Correto!"); add_xp(5)
                    else:
                        st.error(f"Errado. Resposta: {q['correct_answer']}")
                        st.info(q['explanation'])
                    st.session_state.prof_idx += 1
                    st.rerun()
            else:
                st.success("Aula concluída!")

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

        # Ranking completo também aqui
        ranking = conn.execute("""
            SELECT u.user_id, COALESCE(SUM(xp.xp_gained), 0) as total_xp
            FROM users u
            LEFT JOIN xp_log xp ON u.user_id = xp.user_id
            GROUP BY u.user_id
            ORDER BY total_xp DESC
        """).fetchall()
        if ranking:
            st.subheader("🏅 Ranking Geral")
            df_rank = pd.DataFrame(ranking, columns=["Usuário", "XP Total"])
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
                st.session_state.daily_idx = 0
                st.rerun()
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