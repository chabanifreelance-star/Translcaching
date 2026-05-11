import streamlit as st
import sqlite3
import time
import os
import tempfile
from datetime import datetime

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate · Conference",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;800&family=DM+Sans:ital,wght@0,300;0,400;0,500;1,300&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* Background */
.stApp {
    background: #0a0a0f;
    color: #e8e6f0;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #12111a !important;
    border-right: 1px solid #1e1d2e;
}
[data-testid="stSidebar"] * { color: #c8c6d8 !important; }

/* Headers */
h1, h2, h3 {
    font-family: 'Syne', sans-serif !important;
    letter-spacing: -0.02em;
}

/* Role badge */
.role-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.role-speaker { background: #2a1a3e; color: #c084fc; border: 1px solid #6d28d9; }
.role-audience { background: #0f2a2a; color: #34d399; border: 1px solid #059669; }

/* Translation card */
.translation-card {
    background: #13121e;
    border: 1px solid #1e1d2e;
    border-radius: 12px;
    padding: 20px 24px;
    margin: 10px 0;
    position: relative;
    transition: border-color 0.2s;
}
.translation-card:hover { border-color: #3b3a5c; }
.translation-card .timestamp {
    font-size: 11px;
    color: #5a5878;
    font-family: 'DM Mono', monospace;
    margin-bottom: 8px;
}
.translation-card .original {
    font-size: 13px;
    color: #6b6992;
    font-style: italic;
    margin-bottom: 10px;
    padding-bottom: 10px;
    border-bottom: 1px solid #1e1d2e;
}
.translation-card .translated {
    font-size: 18px;
    font-weight: 400;
    color: #e8e6f0;
    line-height: 1.6;
}

/* Live indicator */
.live-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef4444;
    animation: pulse 1.5s infinite;
    margin-right: 8px;
}
@keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(0.8); }
}

/* Status bar */
.status-bar {
    background: #13121e;
    border: 1px solid #1e1d2e;
    border-radius: 8px;
    padding: 12px 18px;
    display: flex;
    align-items: center;
    font-size: 13px;
    color: #8b899e;
    margin: 12px 0;
}

/* Button overrides */
.stButton > button {
    background: #4f46e5 !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    transition: background 0.2s !important;
}
.stButton > button:hover {
    background: #4338ca !important;
}

/* Input / select overrides */
.stTextInput input, .stSelectbox > div > div {
    background: #13121e !important;
    border: 1px solid #1e1d2e !important;
    color: #e8e6f0 !important;
    border-radius: 8px !important;
}

/* Segment count chip */
.count-chip {
    background: #1e1d2e;
    color: #8b899e;
    border-radius: 20px;
    padding: 2px 12px;
    font-size: 12px;
    font-weight: 500;
}

/* Waiting animation */
.waiting {
    text-align: center;
    padding: 60px 20px;
    color: #3b3a5c;
}
.waiting .icon { font-size: 48px; margin-bottom: 16px; }
.waiting p { font-size: 15px; }
</style>
""", unsafe_allow_html=True)

# ─── Languages ───────────────────────────────────────────────────────────────
LANGUAGES = {
    "🇫🇷 French": "fr",
    "🇪🇸 Spanish": "es",
    "🇸🇦 Arabic": "ar",
    "🇩🇪 German": "de",
    "🇨🇳 Chinese (Simplified)": "zh-CN",
    "🇯🇵 Japanese": "ja",
    "🇧🇷 Portuguese": "pt",
    "🇮🇹 Italian": "it",
    "🇷🇺 Russian": "ru",
    "🇮🇳 Hindi": "hi",
    "🇰🇷 Korean": "ko",
    "🇳🇱 Dutch": "nl",
    "🇹🇷 Turkish": "tr",
    "🇵🇱 Polish": "pl",
    "🇸🇪 Swedish": "sv",
    "🇬🇷 Greek": "el",
    "🇹🇭 Thai": "th",
    "🇻🇳 Vietnamese": "vi",
    "🇮🇩 Indonesian": "id",
    "🇺🇦 Ukrainian": "uk",
}

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = "conference_live.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            original  TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_segment(text: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO segments (original, timestamp) VALUES (?, ?)",
        (text, datetime.now().strftime("%H:%M:%S")),
    )
    conn.commit()
    seg_id = c.lastrowid
    conn.close()
    return seg_id

def get_segments(limit: int = 15):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, original, timestamp FROM segments ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def get_segment_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM segments")
    count = c.fetchone()[0]
    conn.close()
    return count

def clear_session():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM segments")
    conn.commit()
    conn.close()

init_db()

# ─── Translation helper ───────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def translate_cached(text: str, lang_code: str) -> str:
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source="auto", target=lang_code).translate(text)
    except Exception as e:
        return f"[Translation error: {e}]"

# ─── Transcription helper (100% free, no API key) ────────────────────────────
def transcribe(audio_bytes: bytes) -> str:
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)
        return recognizer.recognize_google(audio)   # free, no key needed
    except sr.UnknownValueError:
        return ""   # no speech detected
    except sr.RequestError as e:
        raise RuntimeError(f"Google Speech service error: {e}")
    finally:
        os.unlink(tmp_path)

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌐 LiveTranslate")
    st.markdown("*Real-time conference translator*")
    st.divider()

    role = st.radio(
        "**Your role**",
        ["🎤 Speaker", "👥 Audience"],
        help="Speaker records and broadcasts. Audience listens and reads.",
    )
    st.divider()

    if role == "🎤 Speaker":
        st.success("✅ Free mode — no API key needed!")
        st.caption("Powered by Google Speech Recognition (free, no account needed).")

    st.divider()
    count = get_segment_count()
    st.markdown(f"**Session segments:** `{count}`")
    if st.button("🗑️ Clear session", use_container_width=True):
        clear_session()
        st.cache_data.clear()
        st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
#  SPEAKER VIEW
# ═══════════════════════════════════════════════════════════════════════════════
if role == "🎤 Speaker":
    st.markdown('<span class="role-badge role-speaker">Speaker</span>', unsafe_allow_html=True)
    st.markdown("# Record & Broadcast")
    st.markdown("Record a segment of your speech. It will be transcribed and sent live to your audience.")

    col_main, col_history = st.columns([3, 2], gap="large")

    with col_main:
        audio_input = st.audio_input("🎙️ Click to record your segment", key="mic")

        if audio_input:
            with st.spinner("🎙️ Transcribing…"):
                try:
                    text = transcribe(audio_input.getvalue())
                    if text:
                        save_segment(text)
                        st.markdown(
                            f"""<div class="translation-card">
                                <div class="timestamp">✅ Broadcasted at {datetime.now().strftime('%H:%M:%S')}</div>
                                <div class="translated">{text}</div>
                            </div>""",
                            unsafe_allow_html=True,
                        )
                        st.cache_data.clear()
                    else:
                        st.warning("No speech detected — try again.")
                except Exception as e:
                    st.error(f"Transcription failed: {e}")

    with col_history:
        st.markdown("### 📋 Broadcast history")
        segments = get_segments(8)
        if not segments:
            st.markdown(
                '<div class="waiting"><div class="icon">🎙️</div><p>No segments yet. Start recording!</p></div>',
                unsafe_allow_html=True,
            )
        else:
            for seg in reversed(segments):
                st.markdown(
                    f"""<div class="translation-card">
                        <div class="timestamp">{seg[2]}</div>
                        <div class="translated" style="font-size:14px">{seg[1]}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIENCE VIEW
# ═══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown('<span class="role-badge role-audience">Audience</span>', unsafe_allow_html=True)
    st.markdown("# Live Translation")

    top_left, top_right = st.columns([2, 1])

    with top_left:
        lang_name = st.selectbox(
            "🌐 **Your language**",
            list(LANGUAGES.keys()),
            help="Select the language you want to read the speech in.",
        )
        lang_code = LANGUAGES[lang_name]

    with top_right:
        st.markdown("<br>", unsafe_allow_html=True)
        live_mode = st.toggle("🔴 Live mode (auto-refresh)", value=True)
        refresh_rate = st.select_slider(
            "Refresh every",
            options=[2, 3, 5, 10],
            value=3,
            format_func=lambda x: f"{x}s",
            disabled=not live_mode,
        )

    st.divider()

    # Status bar
    count = get_segment_count()
    if live_mode:
        st.markdown(
            f'<div class="status-bar"><span class="live-dot"></span>'
            f'Live · refreshing every {refresh_rate}s &nbsp;·&nbsp; {count} segment(s) received</div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="status-bar">⏸ Paused &nbsp;·&nbsp; {count} segment(s) received</div>',
            unsafe_allow_html=True,
        )

    # Translation display
    segments = get_segments(15)

    if not segments:
        st.markdown(
            '<div class="waiting"><div class="icon">⏳</div>'
            '<p>Waiting for the speaker to start broadcasting…</p></div>',
            unsafe_allow_html=True,
        )
    else:
        for seg in segments:
            seg_id, original, ts = seg
            translated = translate_cached(original, lang_code)

            st.markdown(
                f"""<div class="translation-card">
                    <div class="timestamp">🕐 {ts}</div>
                    <div class="original">EN · {original}</div>
                    <div class="translated">{translated}</div>
                </div>""",
                unsafe_allow_html=True,
            )

    # Auto-refresh
    if live_mode:
        time.sleep(refresh_rate)
        st.rerun()
