#!/usr/bin/env python3
"""
UltraLearn IA – Premium Edition (Visual incrível + Continuação Infinita + Todas as Funcionalidades)
"""
import streamlit as st
import json, os, random, io, base64, hashlib, uuid, time
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
        titulos TEXT DEFAULT '[]',
        unlocked_avatars TEXT DEFAULT '["🧑"]',
        unlocked_frames TEXT DEFAULT '["⬜"]',
        frame_equipped TEXT DEFAULT '⬜'
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

conn.execute("""
    CREATE TABLE IF NOT EXISTS missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        date TEXT,
        mission_type TEXT,
        goal INTEGER DEFAULT 0,
        progress INTEGER DEFAULT 0,
        completed INTEGER DEFAULT 0
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        topic TEXT,
        content TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS avatar_shop (
        avatar TEXT PRIMARY KEY,
        price INTEGER DEFAULT 0
    )
""")

conn.execute("""
    CREATE TABLE IF NOT EXISTS frame_shop (
        frame TEXT PRIMARY KEY,
        price INTEGER DEFAULT 0
    )
""")

# Popula lojas se vazias
avatares_iniciais = [("🧑",0),("👩",0),("👨",0),("🐵",50),("🦊",80),("🐱",80),("🐶",80),("👽",120),("🐉",200),("👑",500)]
for avatar, price in avatares_iniciais:
    conn.execute("INSERT OR IGNORE INTO avatar_shop (avatar, price) VALUES (?,?)", (avatar, price))

molduras_iniciais = [("⬜",0),("🟦",50),("🟩",80),("🟨",80),("🟪",100),("🟧",100),("🔲",150),("🏁",200),("💠",300),("🌀",500)]
for frame, price in molduras_iniciais:
    conn.execute("INSERT OR IGNORE INTO frame_shop (frame, price) VALUES (?,?)", (frame, price))

# Migrações
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN titulos TEXT DEFAULT '[]'")
    conn.commit()
except: pass
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN unlocked_avatars TEXT DEFAULT '[\"🧑\"]'")
    conn.commit()
except: pass
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN unlocked_frames TEXT DEFAULT '[\"⬜\"]'")
    conn.commit()
except: pass
try:
    conn.execute("ALTER TABLE user_data ADD COLUMN frame_equipped TEXT DEFAULT '⬜'")
    conn.commit()
except: pass

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

    /* Molduras */
    .moldura {{
        display: inline-block;
        padding: 5px;
        border-radius: 16px;
    }}
    .moldura-⬜ {{ border: 2px solid #e2e8f0; }}
    .moldura-🟦 {{ border: 3px solid #3b82f6; box-shadow: 0 0 10px #3b82f6; }}
    .moldura-🟩 {{ border: 3px solid #22c55e; box-shadow: 0 0 10px #22c55e; }}
    .moldura-🟨 {{ border: 3px solid #eab308; box-shadow: 0 0 10px #eab308; }}
    .moldura-🟪 {{ border: 3px solid #a855f7; box-shadow: 0 0 10px #a855f7; }}
    .moldura-🟧 {{ border: 3px solid #f97316; box-shadow: 0 0 10px #f97316; }}
    .moldura-🔲 {{ border: 3px dashed #cbd5e1; }}
    .moldura-🏁 {{ border: 4px double #ffffff; }}
    .moldura-💠 {{ border: 3px dotted #06b6d4; }}
    .moldura-🌀 {{ border: 3px solid; border-image: linear-gradient(45deg, #ff6b6b, #4ecdc4, #45b7d1) 1; }}

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
            "user_id": row[0], "xp": row[1], "streak": row[2],
            "last_daily": row[3],
            "achievements": json.loads(row[4]) if row[4] else [],
            "titulos": json.loads(row[5]) if len(row)>5 and row[5] else [],
            "unlocked_avatars": json.loads(row[6]) if len(row)>6 and row[6] else ["🧑"],
            "unlocked_frames": json.loads(row[7]) if len(row)>7 and row[7] else ["⬜"],
            "frame_equipped": row[8] if len(row)>8 and row[8] else "⬜"
        }
    else:
        default = {"user_id": USER_ID, "xp": 0, "streak": 0, "last_daily": None,
                   "achievements": [], "titulos": [], "unlocked_avatars": ["🧑"],
                   "unlocked_frames": ["⬜"], "frame_equipped": "⬜"}
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
        new_streak = data["streak"] + 1 if data["last_daily"] == (date.today()-timedelta(days=1)).isoformat() else 1
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

# Missões
def gerar_missoes_diarias():
    today = date.today().isoformat()
    exist = conn.execute("SELECT id FROM missions WHERE user_id=? AND date=?", (USER_ID, today)).fetchone()
    if not exist:
        missoes = [("quiz_normal", random.randint(3,5)), ("quiz_primata", 1), ("exportar_pdf", 1), ("usar_continuacao", 2), ("comentar", 1)]
        for tipo, meta in missoes:
            conn.execute("INSERT INTO missions (user_id, date, mission_type, goal) VALUES (?,?,?,?)", (USER_ID, today, tipo, meta))
        conn.commit()

def atualizar_progresso_missao(tipo, incremento=1):
    today = date.today().isoformat()
    conn.execute("UPDATE missions SET progress = progress + ? WHERE user_id=? AND date=? AND mission_type=? AND completed=0", (incremento, USER_ID, today, tipo))
    conn.commit()
    missao = conn.execute("SELECT id, goal, progress FROM missions WHERE user_id=? AND date=? AND mission_type=? AND completed=0", (USER_ID, today, tipo)).fetchone()
    if missao and missao[2] >= missao[1]:
        conn.execute("UPDATE missions SET completed=1 WHERE id=?", (missao[0],))
        conn.commit()
        add_xp(15)
        st.toast(f"🎯 Missão concluída: {tipo}!")

# Loja de avatares e molduras
def comprar_item(tipo, item):
    data = load_user_data()
    if tipo == "avatar":
        shop_table, col_name, unlocked_col = "avatar_shop", "avatar", "unlocked_avatars"
    else:
        shop_table, col_name, unlocked_col = "frame_shop", "frame", "unlocked_frames"
    price = conn.execute(f"SELECT price FROM {shop_table} WHERE {col_name}=?", (item,)).fetchone()
    if not price:
        return False, "Item não encontrado."
    price = price[0]
    if item in data[unlocked_col]:
        return False, "Você já possui este item."
    if data["xp"] < price:
        return False, f"XP insuficiente. Você precisa de {price} XP."
    new_xp = data["xp"] - price
    unlocked = data[unlocked_col] + [item]
    updates = {"xp": new_xp, unlocked_col: json.dumps(unlocked)}
    save_user_data(updates)
    return True, f"{'Avatar' if tipo=='avatar' else 'Moldura'} {item} adquirido!"

def equipar_moldura(frame):
    save_user_data({"frame_equipped": frame})

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

# ---------- Componentes de quiz ----------
def show_quiz(questions, mode="normal"):
    idx = st.session_state.get("quiz_index", 0)
    total = len(questions)

    if mode == "sobrevivência":
        if "lives" not in st.session_state: st.session_state.lives = 3
        st.sidebar.metric("❤️ Vidas", st.session_state.lives)
    if mode == "relâmpago":
        if "time_left" not in st.session_state: st.session_state.time_left = 10
        st.progress(st.session_state.time_left / 10)
        st.caption(f"⏳ {st.session_state.time_left}s restantes")

    if idx >= total:
        st.balloons()
        if mode == "sobrevivência":
            st.success(f"Sobrevivência concluída! Vidas restantes: {st.session_state.lives}")
            add_xp(st.session_state.quiz_score * 15 + st.session_state.lives * 10)
        else:
            st.success(f"Quiz concluído! Acertos: {st.session_state.quiz_score}/{total}")
            add_xp(st.session_state.quiz_score * 10)
        if st.button("Limpar Quiz"):
            for key in ["quiz_questions","quiz_index","quiz_score","lives","time_left"]:
                if key in st.session_state: del st.session_state[key]
            st.rerun()
        return

    q = questions[idx]
    st.subheader(q['question'])
    if q["type"] == "multiple_choice":
        opt = st.radio("Opções", q['options'], index=None)
    else:
        opt = st.radio("V/F", ["Verdadeiro","Falso"], index=None)
    if st.button("Responder") and opt:
        user = opt.split('.')[0].strip() if q["type"]=="multiple_choice" else ("Verdadeiro" if opt=="Verdadeiro" else "Falso")
        correct = q['correct_answer']
        if user == correct:
            st.session_state.quiz_score += 1
            st.success("Correto!")
        else:
            st.error(f"Errado. Resposta: {correct}")
            st.info(q['explanation'])
            if mode == "sobrevivência":
                st.session_state.lives -= 1
                if st.session_state.lives <= 0:
                    st.error("💀 Você perdeu todas as vidas!")
                    st.session_state.quiz_index = total
                    st.rerun()
        st.session_state.quiz_index += 1
        if mode == "relâmpago":
            st.session_state.time_left = 10
        st.rerun()
    if mode == "relâmpago":
        st.session_state.time_left -= 1
        if st.session_state.time_left <= 0:
            st.error("⏰ Tempo esgotado!")
            st.session_state.quiz_index += 1
            st.session_state.time_left = 10
            st.rerun()
        time.sleep(1)
        st.rerun()

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
    defaults = {
        "explanation": "", "topic": "", "primata_explanation": "",
        "quiz_questions": [], "quiz_index": 0, "quiz_score": 0,
        "quiz_active": False, "quiz_feedback": None, "quiz_mode": "normal",
        "flashcards": [], "theme": "dark", "pomodoro_seconds": 0,
        "pomodoro_active": False, "font_size": 16, "daltonic": None,
        "story_state": None, "prof_questions": [], "prof_idx": 0,
        "daily_questions": [], "daily_idx": 0,
        "caotico_questions": [], "caos_idx": 0, "caos_score": 0,
        "lives": 3, "time_left": 10
    }
    for k, v in defaults.items():
        if k not in st.session_state: st.session_state[k] = v

    gerar_missoes_diarias()

    with st.sidebar:
        st.image("https://i.imgur.com/cfSvLdE.png", width=200)
        st.markdown("---")
        st.markdown("## 👤 Meu Perfil")
        user_row = conn.execute("SELECT avatar, bio FROM users WHERE user_id = ?", (USER_ID,)).fetchone()
        avatar, bio = user_row if user_row else ("🧑", "")
        data = load_user_data()
        avatares_disponiveis = data["unlocked_avatars"]
        avatar_escolhido = st.selectbox("Avatar", avatares_disponiveis, index=avatares_disponiveis.index(avatar) if avatar in avatares_disponiveis else 0)
        if avatar_escolhido != avatar:
            conn.execute("UPDATE users SET avatar=? WHERE user_id=?", (avatar_escolhido, USER_ID))
            conn.commit()
            st.rerun()
        # Moldura equipada
        frame_equipped = data["frame_equipped"]
        st.markdown(f'<div class="moldura moldura-{frame_equipped}"><span style="font-size:3rem;">{avatar_escolhido}</span></div>', unsafe_allow_html=True)
        st.write(bio)
        if st.button("🚪 Sair"):
            cookie_token = cookies.get("ultralearn_token")
            if cookie_token: remover_token(cookie_token)
            cookies["ultralearn_token"] = ""
            cookies.save()
            st.session_state.logged_in = False
            st.session_state.user_id = None
            st.rerun()

        st.markdown("---")
        st.markdown("## 🛒 Loja de Avatares")
        shop_avatars = conn.execute("SELECT avatar, price FROM avatar_shop WHERE avatar NOT IN (SELECT value FROM json_each(?))", (json.dumps(avatares_disponiveis),)).fetchall()
        if shop_avatars:
            for av, price in shop_avatars:
                if st.button(f"{av} ({price} XP)", key=f"buy_av_{av}"):
                    ok, msg = comprar_item("avatar", av)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        else:
            st.write("Todos avatares desbloqueados!")

        st.markdown("---")
        st.markdown("## 🖼️ Loja de Molduras")
        unlocked_frames = data["unlocked_frames"]
        shop_frames = conn.execute("SELECT frame, price FROM frame_shop WHERE frame NOT IN (SELECT value FROM json_each(?))", (json.dumps(unlocked_frames),)).fetchall()
        if shop_frames:
            for frame, price in shop_frames:
                if st.button(f"{frame} ({price} XP)", key=f"buy_fr_{frame}"):
                    ok, msg = comprar_item("frame", frame)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
        else:
            st.write("Todas molduras desbloqueadas!")
        if len(unlocked_frames) > 1:
            nova_moldura = st.selectbox("Equipar moldura", unlocked_frames, index=unlocked_frames.index(frame_equipped) if frame_equipped in unlocked_frames else 0)
            if nova_moldura != frame_equipped:
                equipar_moldura(nova_moldura)
                st.rerun()

        st.markdown("---")
        st.markdown("## ⚙️ Aparência")
        theme = st.selectbox("Tema", ["dark","light","ocean","sunset","forest","neon","marshmallow","midnight","aurora","coffee","cyberpunk"], index=0)
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

        # Missões diárias
        st.markdown("---")
        st.markdown("### 🎯 Missões de Hoje")
        today = date.today().isoformat()
        missoes = conn.execute("SELECT mission_type, goal, progress, completed FROM missions WHERE user_id=? AND date=?", (USER_ID, today)).fetchall()
        if missoes:
            for tipo, meta, prog, comp in missoes:
                st.write(f"{'✅' if comp else '⬜'} {tipo}: {prog}/{meta}")
        else:
            st.write("Nenhuma missão gerada.")

        # Ranking
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
            for _, row in pd.DataFrame(ranking, columns=["Usuário", "XP Total"]).iterrows():
                user = row['Usuário']
                perfil = conn.execute("SELECT avatar, frame_equipped FROM user_data WHERE user_id=?", (user,)).fetchone()
                av = (conn.execute("SELECT avatar FROM users WHERE user_id=?", (user,)).fetchone() or ("🧑",))[0]
                frame = perfil[1] if perfil and perfil[1] else "⬜"
                if st.button(f"{av} {user} ({row['XP Total']} XP)", key=f"rank_{user}"):
                    with st.expander(f"Perfil de {user}", expanded=True):
                        perfil_data = conn.execute("SELECT bio, achievements FROM user_data WHERE user_id=?", (user,)).fetchone()
                        if perfil_data:
                            st.write(f"**Bio:** {perfil_data[0]}")
                            st.write(f"🏆 Conquistas: {', '.join(json.loads(perfil_data[1])) if perfil_data[1] else 'Nenhuma'}")
                        else:
                            st.write("Perfil não encontrado.")

    st.markdown('<div class="main-header"><h1>🧠 UltraLearn IA</h1><p>Domine qualquer assunto com inteligência artificial</p></div>', unsafe_allow_html=True)

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
                    atualizar_progresso_missao("usar_continuacao")
                st.rerun()
            if st.button("Gerar Resumão"):
                st.markdown(f"**Resumo:** {gen_resumo(st.session_state.explanation)}")
            d = st.selectbox("Dificuldade", ["Fácil","Médio","Difícil"], index=1)
            n = st.number_input("Perguntas", 1,20,5)
            if st.button("Criar Quiz"):
                st.session_state.quiz_questions = gen_quiz(st.session_state.explanation, d, n)
                st.session_state.quiz_index = 0; st.session_state.quiz_active = True
                st.session_state.quiz_mode = "normal"
                atualizar_progresso_missao("quiz_normal")
                st.rerun()

    # Aba Aula Completa
    with tabs[1]:
        st.subheader("🎓 Aula Completa")
        top_aula = st.text_input("Tópico:", key="aula_topic")
        if st.button("Iniciar Aula Completa") and top_aula:
            exp = gen_explanation(top_aula); st.markdown(exp); add_xp(5)
            quiz = gen_quiz(exp, "médio", 5)
            if quiz:
                st.session_state.quiz_questions = quiz; st.session_state.quiz_index = 0; st.session_state.quiz_score = 0; st.session_state.quiz_active = True; st.session_state.quiz_mode = "normal"
                st.rerun()
        if st.session_state.quiz_active and st.session_state.quiz_questions:
            show_quiz(st.session_state.quiz_questions, st.session_state.quiz_mode)

    # Aba Quiz (com modos: Normal, Caótico, Maratona, Sobrevivência, Relâmpago)
    with tabs[2]:
        st.subheader("🧠 Modos de Quiz")
        quiz_mode = st.radio("Escolha:", ["Normal", "Caótico (V/F)", "Maratona de Revisão", "Sobrevivência", "Relâmpago"])
        if quiz_mode == "Normal":
            st.session_state.quiz_mode = "normal"
            if st.session_state.quiz_active and st.session_state.quiz_questions:
                show_quiz(st.session_state.quiz_questions, "normal")
            else: st.info("Crie um quiz na aba Estudar.")
        elif quiz_mode == "Caótico (V/F)":
            if "caotico_questions" not in st.session_state: st.session_state.caotico_questions = []
            top_caos = st.text_input("Tópico para quiz caótico:")
            if st.button("Gerar Quiz Caótico") and top_caos:
                prompt = f"Crie 10 afirmações sobre '{top_caos}', metade verdadeiras e metade falsas. JSON com 'questions'."
                resp = client.chat.completions.create(model="llama-3.3-70b-versatile", messages=[{"role":"user","content": prompt}], temperature=0.9, max_tokens=1000)
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
                    add_xp(st.session_state.caos_score * 5)
        elif quiz_mode == "Maratona de Revisão":
            due = [q for q in load_questions() if q.get("next_review") and q["next_review"] <= date.today().isoformat()]
            if due:
                if st.button(f"Revisar {len(due)} questões"):
                    st.session_state.quiz_questions = due; st.session_state.quiz_index = 0; st.session_state.quiz_score = 0; st.session_state.quiz_active = True; st.session_state.quiz_mode = "normal"
                    st.rerun()
                if st.session_state.quiz_active: show_quiz(st.session_state.quiz_questions, "normal")
            else: st.success("Nenhuma revisão pendente!")
        elif quiz_mode == "Sobrevivência":
            st.session_state.quiz_mode = "sobrevivência"
            if st.session_state.quiz_active and st.session_state.quiz_questions:
                show_quiz(st.session_state.quiz_questions, "sobrevivência")
            else: st.info("Gere um quiz primeiro.")
        elif quiz_mode == "Relâmpago":
            st.session_state.quiz_mode = "relâmpago"
            if st.session_state.quiz_active and st.session_state.quiz_questions:
                show_quiz(st.session_state.quiz_questions, "relâmpago")
            else: st.info("Gere um quiz primeiro.")

    # Aba Primata
    with tabs[3]:
        st.subheader("🐵 Aprendendo como um Primata")
        st.image("https://i.imgur.com/dDnr8pn.png", width=300)
        estilos = ["Normal","Rapper","Conspiração","Shakespeare","Stand-Up","ELI5","Poesia"]
        estilo = st.selectbox("Estilo do Macaco:", estilos)
        pt = st.text_input("Tópico primata:", key="ptopic")
        if st.button("Macaco Sábio") and pt:
            chave = estilo.lower().replace("-","")
            st.session_state.primata_explanation = gen_primata(pt, chave)
            add_xp(10); atualizar_progresso_missao("quiz_primata")
            st.rerun()
        if st.session_state.primata_explanation:
            st.markdown(f'<div class="primata-box">{st.session_state.primata_explanation}</div>', unsafe_allow_html=True)

    # As demais abas (Mapa Mental, Debate, História, Música, Redação, Professor, Progresso, Diário)
    # permanecem exatamente como estavam no código anterior, sem alterações.
    # ... (mantenha o código original dessas abas aqui)