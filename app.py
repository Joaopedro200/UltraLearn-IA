#!/usr/bin/env python3
"""
UltraLearn IA – Versão Completa com Turso (Banco de Dados na Nuvem)
"""
import streamlit as st
import json, os, random, io, base64, time
from datetime import datetime, timedelta, date
from groq import Groq
from gtts import gTTS
from fpdf import FPDF
import libsql

# ---------- Configuração da página ----------
st.set_page_config(page_title="UltraLearn IA", page_icon="🧠", layout="centered")

# ---------- CSS customizado ----------
def inject_css(theme="dark"):
    if theme == "dark":
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#0f172a", "#e2e8f0", "#1e293b", "#fef3c7", "#78350f",
            "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)", "linear-gradient(135deg, #3b82f6, #2563eb)"
        )
    else:
        bg_main, text_color, card_bg, primata_bg, primata_text, header_bg, button_bg = (
            "#ffffff", "#1e293b", "#f8fafc", "#fff7ed", "#7c2d12",
            "linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%)", "linear-gradient(135deg, #2563eb, #1d4ed8)"
        )

    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; background-color: {bg_main}; color: {text_color}; }}
    .main-header {{
        background: {header_bg}; padding: 2rem; border-radius: 16px; margin-bottom: 2rem;
        border: 1px solid rgba(0,0,0,0.1); box-shadow: 0 10px 30px -10px rgba(0,0,0,0.3);
    }}
    .main-header h1 {{ color: {text_color}; font-size: 2.5rem; }}
    .explanation-box, .quiz-card {{ background: {card_bg}; border: 1px solid #334155; border-radius: 16px; padding: 2rem; margin: 1.5rem 0; }}
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

# ---------- Conexão com Turso ----------
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")
if not TURSO_URL or not TURSO_TOKEN:
    st.error("Configure TURSO_DATABASE_URL e TURSO_AUTH_TOKEN nos Secrets do Streamlit Cloud.")
    st.stop()

conn = libsql.connect("ultralearn.db", sync_url=TURSO_URL, auth_token=TURSO_TOKEN)
conn.sync()  # sincroniza o estado remoto na primeira carga

# Cria as tabelas se não existirem
conn.execute("""
    CREATE TABLE IF NOT EXISTS user_data (
        user_id TEXT PRIMARY KEY, xp INTEGER DEFAULT 0, streak INTEGER DEFAULT 0,
        last_daily TEXT, achievements TEXT DEFAULT '[]'
    )
""")
conn.execute("""
    CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, question TEXT, type TEXT,
        options TEXT, correct_answer TEXT, explanation TEXT, interval INTEGER DEFAULT 1,
        ease_factor REAL DEFAULT 2.5, next_review TEXT
    )
""")
conn.commit()
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# ---------- Estados da sessão ----------
session_defaults = {
    "explanation": "", "topic": "", "primata_explanation": "",
    "quiz_questions": [], "quiz_index": 0, "quiz_score": 0,
    "quiz_active": False, "quiz_feedback": None,
    "flashcards": [], "theme": "dark", "pomodoro_seconds": 0,
    "pomodoro_active": False
}
for k, v in session_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ---------- Funções de IA (sem alterações) ----------
def gen_explanation(topic):
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content":f"Explique '{topic}' em português, 3 parágrafos detalhados."}], temperature=0.7, max_tokens=1500)
    return resp.choices[0].message.content.strip()

def gen_primata(topic, style="normal"):
    prompts = {
        "normal": f"Macaco professor explica '{topic}' em português, aula completa e divertida, 5+ parágrafos.",
        "rapper": f"Macaco rapper explica '{topic}' em forma de rap rimado em português. Use muitas gírias e batida de rap.",
        "conspiracy": f"Macaco conspirador explica '{topic}' como uma teoria da conspiração maluca e engraçada em português.",
        "shakespeare": f"Macaco shakesperiano explica '{topic}' em português arcaico, estilo William Shakespeare."
    }
    resp = client.chat.completions.create(model="llama-3.3-70b-versatile",
        messages=[{"role":"user","content": prompts[style]}], temperature=0.9, max_tokens=2500)
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

# ---------- Persistência (agora no Turso) ----------
USER_ID = "default"

def load_user_data():
    row = conn.execute("SELECT * FROM user_data WHERE user_id = ?", (USER_ID,)).fetchone()
    if row:
        return {"user_id": row[0], "xp": row[1], "streak": row[2], "last_daily": row[3], "achievements": json.loads(row[4])}
    else:
        conn.execute("INSERT INTO user_data(user_id) VALUES (?)", (USER_ID,))
        conn.commit()
        return {"user_id": USER_ID, "xp": 0, "streak": 0, "last_daily": None, "achievements": []}

def save_user_data(updates):
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values())
    conn.execute(f"UPDATE user_data SET {sets} WHERE user_id = ?", (*vals, USER_ID))
    conn.commit()

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
    # Procura se a questão já existe
    existing = conn.execute("SELECT id, interval, ease_factor FROM questions WHERE question = ? AND user_id = ?", (question["question"], USER_ID)).fetchone()
    if existing:
        interval, ease = existing[1], existing[2]
        if quality >= 3:
            interval = int(interval * ease)
            ease += 0.1
        else:
            interval = 1
            ease = max(1.3, ease - 0.2)
        next_review = (now + timedelta(days=interval)).strftime("%Y-%m-%d")
        conn.execute("UPDATE questions SET interval = ?, ease_factor = ?, next_review = ? WHERE id = ?", (interval, ease, next_review, existing[0]))
    else:
        next_review = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        conn.execute(
            "INSERT INTO questions(user_id, question, type, options, correct_answer, explanation, interval, ease_factor, next_review) VALUES (?,?,?,?,?,?,1,2.5,?)",
            (USER_ID, question["question"], question["type"], json.dumps(question.get("options", [])), question["correct_answer"], question.get("explanation", ""), next_review)
        )
    conn.commit()

def add_xp(amount):
    data = load_user_data()
    new_xp = data["xp"] + amount
    save_user_data({"xp": new_xp})
    achievements = data["achievements"]
    if new_xp >= 100 and "Centenário" not in achievements:
        achievements.append("Centenário")
        save_user_data({"achievements": json.dumps(achievements)})
        st.balloons()
        st.success("🏆 Conquista desbloqueada: Centenário (100 XP)")
    if new_xp >= 500 and "Quinhentão" not in achievements:
        achievements.append("Quinhentão")
        save_user_data({"achievements": json.dumps(achievements)})
        st.balloons()
        st.success("🏆 Conquista desbloqueada: Quinhentão (500 XP)")

def update_daily_streak():
    data = load_user_data()
    today = date.today().isoformat()
    if data["last_daily"] != today:
        new_streak = data["streak"] + 1 if data["last_daily"] == (date.today() - timedelta(days=1)).isoformat() else 1
        save_user_data({"streak": new_streak, "last_daily": today})
        return new_streak
    return data["streak"]

def generate_flashcards(questions):
    return [(q["question"], q["correct_answer"] + " - " + q.get("explanation", "")) for q in questions]

def export_quiz_pdf(questions):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    for i, q in enumerate(questions):
        pdf.multi_cell(0, 10, f"Q{i+1}: {q['question']}")
        if q["type"] == "multiple_choice":
            for opt in q["options"]:
                pdf.cell(0, 10, opt, ln=True)
        else:
            pdf.cell(0, 10, "Verdadeiro ou Falso", ln=True)
        pdf.cell(0, 10, f"Resposta: {q['correct_answer']}", ln=True)
        pdf.ln(5)
    return pdf.output(dest="S").encode("latin-1")

def text_to_speech(text):
    tts = gTTS(text, lang='pt')
    fp = io.BytesIO()
    tts.write_to_fp(fp)
    fp.seek(0)
    return fp

# ---------- Componentes (idênticos à versão anterior) ----------
def show_quiz():
    idx = st.session_state.quiz_index
    total = len(st.session_state.quiz_questions)
    if idx >= total:
        st.balloons()
        st.success(f"Quiz concluído! Acertos: {st.session_state.quiz_score}/{total}")
        add_xp(st.session_state.quiz_score * 10)
        if st.button("Limpar Quiz"):
            st.session_state.quiz_questions=[]; st.session_state.quiz_index=0; st.rerun()
        if st.button("Gerar Flashcards"):
            st.session_state.flashcards = generate_flashcards(st.session_state.quiz_questions)
            st.rerun()
        if st.button("Exportar Quiz em PDF"):
            pdf_bytes = export_quiz_pdf(st.session_state.quiz_questions)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="quiz.pdf">Clique aqui para baixar o PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
        return
    q = st.session_state.quiz_questions[idx]
    st.progress(idx/total); st.caption(f"Questão {idx+1}/{total}")
    with st.container():
        st.markdown('<div class="quiz-card">', unsafe_allow_html=True)
        st.subheader(q['question'])
        if q["type"]=="multiple_choice":
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

def show_flashcards():
    if not st.session_state.flashcards: return
    for i, (front, back) in enumerate(st.session_state.flashcards):
        with st.expander(f"Flashcard {i+1}: {front}"):
            st.write(f"**Resposta:** {back}")

def pomodoro_timer():
    if st.session_state.pomodoro_active and st.session_state.pomodoro_seconds > 0:
        st.session_state.pomodoro_seconds -= 1
        mins, secs = divmod(st.session_state.pomodoro_seconds, 60)
        st.sidebar.metric("⏳ Pomodoro", f"{mins:02d}:{secs:02d}")
        time.sleep(1)
        st.rerun()
    elif st.session_state.pomodoro_seconds == 0:
        st.sidebar.success("Pomodoro concluído!")
        st.session_state.pomodoro_active = False
        st.balloons()

# ---------- Interface principal ----------
def main():
    with st.sidebar:
        st.markdown("## ⚙️ Configurações")
        theme = st.toggle("Modo Escuro", value=st.session_state.theme=="dark")
        st.session_state.theme = "dark" if theme else "light"
        inject_css(st.session_state.theme)

        st.markdown("---")
        st.markdown("### ⏱️ Pomodoro")
        if st.button("Iniciar 25 min"):
            st.session_state.pomodoro_seconds = 25*60
            st.session_state.pomodoro_active = True
        pomodoro_timer()

        st.markdown("---")
        data = load_user_data()
        st.metric("XP Total", data["xp"])
        st.metric("Streak Diário", f"{data['streak']} dias")
        if data["achievements"]:
            st.markdown("**🏆 Conquistas:**")
            for a in data["achievements"]:
                st.write(f"- {a}")

    st.markdown('<div class="main-header"><h1>🧠 UltraLearn IA</h1><p>Aprenda com estilo!</p></div>', unsafe_allow_html=True)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "📖 Ensinar", "🧠 Quiz", "🐵 Primata", "✍️ Redação", "👨‍🏫 Professor", "📊 Dashboard", "📅 Diário"
    ])

    with tab1:
        topic = st.text_input("Assunto:", key="topic")
        if st.button("Gerar Explicação") and topic:
            st.session_state.explanation = gen_explanation(topic)
            add_xp(5)
            st.rerun()
        if st.session_state.explanation:
            st.markdown(f'<div class="explanation-box">{st.session_state.explanation}</div>', unsafe_allow_html=True)
            if st.button("🔊 Ouvir Explicação"):
                audio = text_to_speech(st.session_state.explanation)
                st.audio(audio, format='audio/mp3')
            d = st.selectbox("Dificuldade",["Fácil","Médio","Difícil"],index=1)
            n = st.number_input("Perguntas",1,20,5)
            if st.button("Criar Quiz"):
                st.session_state.quiz_questions = gen_quiz(st.session_state.explanation, d, n)
                st.session_state.quiz_index = 0
                st.rerun()

    with tab2:
        if st.session_state.quiz_active or st.session_state.quiz_questions:
            show_quiz()
        else:
            st.info("Crie um quiz na aba Ensinar.")
        if st.session_state.flashcards:
            show_flashcards()

    with tab3:
        primata_style = st.radio("Estilo do Macaco:", ["Normal", "Rapper", "Conspiração", "Shakespeare"], index=0)
        pt = st.text_input("Tópico primata:", key="ptopic")
        if st.button("Macaco Sábio") and pt:
            style_map = {"Normal":"normal","Rapper":"rapper","Conspiração":"conspiracy","Shakespeare":"shakespeare"}
            st.session_state.primata_explanation = gen_primata(pt, style_map[primata_style])
            add_xp(10)
            st.rerun()
        if st.session_state.primata_explanation:
            st.markdown(f'<div class="primata-box">{st.session_state.primata_explanation}</div>', unsafe_allow_html=True)

    with tab4:
        st.subheader("✍️ Modo Redação Assistida")
        redacao = st.text_area("Escreva sua redação:", height=200)
        if st.button("Avaliar Redação") and redacao:
            avaliacao = gen_redacao_avaliacao(redacao)
            st.markdown(f"### Avaliação da IA:\n{avaliacao}")
            add_xp(15)

    with tab5:
        st.subheader("👨‍🏫 Modo Professor vs Aluno")
        ptopic_prof = st.text_input("Tópico para aula:", key="prof_topic")
        if "prof_questions" not in st.session_state:
            st.session_state.prof_questions = []
        if st.button("Iniciar Aula") and ptopic_prof:
            st.session_state.prof_questions = gen_quiz(gen_explanation(ptopic_prof), "médio", 5)
            st.session_state.prof_idx = 0
        if st.session_state.prof_questions:
            idx = st.session_state.prof_idx
            if idx < len(st.session_state.prof_questions):
                q = st.session_state.prof_questions[idx]
                st.write(f"**Pergunta:** {q['question']}")
                user_answer = st.text_input("Sua resposta:", key=f"prof_ans_{idx}")
                if st.button("Enviar Resposta"):
                    correct = q['correct_answer']
                    if user_answer.lower() == correct.lower():
                        st.success("Correto!"); add_xp(5)
                    else:
                        st.error(f"Errado. Resposta correta: {correct}")
                        st.info(f"Explicação: {q['explanation']}")
                    st.session_state.prof_idx += 1
                    st.rerun()
            else:
                st.success("Aula concluída!")

    with tab6:
        st.subheader("📊 Seu Progresso")
        data = load_user_data()
        st.metric("Total de XP", data["xp"])
        st.metric("Streak Atual", data["streak"])
        st.write("Conquistas:", data["achievements"])
        due = [q for q in load_questions() if q.get("next_review", "") <= date.today().isoformat()]
        st.metric("Questões para Revisar Hoje", len(due))

    with tab7:
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
                st.write(f"**{q['question']}**")
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

if __name__ == "__main__":
    main()