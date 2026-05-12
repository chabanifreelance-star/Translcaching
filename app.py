"""
LiveTranslate Conference — v7 (Room System, No QR, Perfect Translation)
==========================================================================
requirements.txt:
  streamlit>=1.37
  faster-whisper
  deep-translator
  numpy

Run locally:
  pip install streamlit faster-whisper deep-translator numpy
  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import sqlite3, os, tempfile, time, random, string
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide all Streamlit chrome
st.markdown("""
<style>
#MainMenu,header,footer,[data-testid="stSidebar"],[data-testid="collapsedControl"],
[data-testid="stStatusWidget"]{display:none!important;visibility:hidden!important;}
.stApp{background:#080808!important;}
.block-container{padding:0!important;max-width:100%!important;}
.stButton>button{
  border-radius:10px!important;font-weight:700!important;
  background:#161616!important;border:1px solid #2a2a2a!important;
  color:#f2ede3!important;font-size:14px!important;
  padding:12px 8px!important;
}
.stButton>button:hover{
  background:#1e1e1e!important;border-color:#3a3a3a!important;
}
/* Kill gap between iframe and next element */
iframe{display:block!important;margin:0!important;padding:0!important;}
[data-testid="stVerticalBlock"]{gap:0!important;}
div[data-testid="column"]{padding:0 4px!important;}
/* text input styling */
.stTextInput>div>div>input{
  background:#161616!important;border:1px solid #2a2a2a!important;
  color:#f2ede3!important;border-radius:10px!important;
  font-size:20px!important;text-align:center!important;
  letter-spacing:6px!important;font-weight:700!important;
  font-family:monospace!important;padding:14px!important;
}
.stTextInput label{color:#555!important;font-size:11px!important;letter-spacing:.1em!important;}
body,html{overflow-x:hidden!important;max-width:100vw!important;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED CSS for components.html iframes
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');
:root{
  --bg:#080808; --s:#101010; --card:#161616; --card2:#1c1c1c;
  --b:#222; --b2:#2e2e2e;
  --white:#f2ede3; --muted:#555; --dim:#2a2a2a;
  --green:#007a3d; --gl:#00c65e;
  --red:#ce1126;   --rl:#ff3348;
  --melon:#fd6b4b; --ml:#ff8a6a;
  --amber:#f59e0b;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{background:transparent;color:var(--white);
  font-family:'Cairo',sans-serif;-webkit-font-smoothing:antialiased;
  overflow-x:hidden;}
a{text-decoration:none;color:inherit;}
::-webkit-scrollbar{width:3px;}
::-webkit-scrollbar-track{background:#0a0a0a;}
::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:2px;}
</style>
"""

FLAG_BAR = """
<style>
body::before{content:'';position:fixed;top:0;left:0;right:0;height:3px;z-index:99;
  background:linear-gradient(90deg,var(--red) 25%,#111 25%,#111 50%,
  var(--green) 50%,var(--green) 75%,#111 75%);}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE  — per-room isolation
# ─────────────────────────────────────────────────────────────────────────────
DB = os.path.join(tempfile.gettempdir(), "lt_v7.db")

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    try:
        with _cx() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS seg(
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                room    TEXT    NOT NULL,
                txt     TEXT    NOT NULL,
                lang    TEXT    DEFAULT '',
                ts      TEXT    NOT NULL
            )""")
            c.execute("""CREATE TABLE IF NOT EXISTS rooms(
                code    TEXT    PRIMARY KEY,
                created TEXT    NOT NULL
            )""")
            c.commit()
    except Exception as e:
        st.error(f"DB init error: {e}")

def room_create(code: str):
    try:
        with _cx() as c:
            c.execute("INSERT OR IGNORE INTO rooms(code,created) VALUES(?,?)",
                      (code, datetime.now().strftime("%H:%M")))
            c.commit()
        return True
    except Exception:
        return False

def room_exists(code: str) -> bool:
    try:
        with _cx() as c:
            r = c.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone()
            return r is not None
    except Exception:
        return False

def db_save(room: str, txt: str, lang: str):
    try:
        with _cx() as c:
            c.execute("INSERT INTO seg(room,txt,lang,ts) VALUES(?,?,?,?)",
                      (room, txt.strip(), lang, datetime.now().strftime("%H:%M")))
            c.commit()
        return True
    except Exception:
        return False

def db_all(room: str, limit=40):
    try:
        with _cx() as c:
            return c.execute(
                "SELECT txt,lang,ts FROM seg WHERE room=? ORDER BY id DESC LIMIT ?",
                (room, limit)
            ).fetchall()
    except Exception:
        return []

def db_count(room: str):
    try:
        with _cx() as c:
            return c.execute(
                "SELECT COUNT(*) FROM seg WHERE room=?", (room,)
            ).fetchone()[0]
    except Exception:
        return 0

def db_clear(room: str):
    try:
        with _cx() as c:
            c.execute("DELETE FROM seg WHERE room=?", (room,))
            c.commit()
    except Exception:
        pass

def gen_code() -> str:
    """Generate a random 4-digit room code."""
    return "".join(random.choices(string.digits, k=4))

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# WHISPER  — cached model, explicit language
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_whisper():
    try:
        from faster_whisper import WhisperModel
        try:
            return WhisperModel("base", device="cuda", compute_type="float16")
        except Exception:
            return WhisperModel("base", device="cpu", compute_type="int8")
    except Exception:
        return None

def transcribe(audio_bytes: bytes, lang_code: str) -> tuple[str, str]:
    model = get_whisper()
    if not model:
        return "", lang_code
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            tmp = f.name
        segs, _ = model.transcribe(
            tmp,
            task="transcribe",
            language=lang_code,          # explicit language — no guessing
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        return text, lang_code
    except Exception:
        return "", lang_code
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION — perfect: always pass known source language, never "auto"
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def tr(text: str, target: str, source: str) -> str:
    """
    Translate `text` from `source` → `target`.
    source must be an explicit language code (never 'auto') so Google
    Translate never mis-detects the language and produces garbage output.
    """
    if not text or not text.strip():
        return text

    # Normalise codes: "zh-CN" → "zh-CN" (keep as-is for zh variants),
    # others strip region ("en-US" → "en").
    def norm(code: str) -> str:
        c = code.strip().lower()
        # preserve zh-CN, zh-TW as Google needs the region
        if c.startswith("zh"):
            return code
        return c.split("-")[0]

    src = norm(source)
    tgt = norm(target)

    if src == tgt:
        return text

    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=src, target=tgt).translate(text)
        return result if result else text
    except Exception as e:
        # return original rather than an ugly error string
        return text

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE LISTS
# ─────────────────────────────────────────────────────────────────────────────
SPEAKER_LANGS = {
    "🇬🇧 English":       "en",
    "🇸🇦 Arabic / عربي": "ar",
    "🇫🇷 French":        "fr",
    "🇹🇷 Turkish":       "tr",
    "🇪🇸 Spanish":       "es",
    "🇩🇪 German":        "de",
    "🇮🇹 Italian":       "it",
    "🇷🇺 Russian":       "ru",
}

AUDIENCE_LANGS = {
    "🇸🇦 Arabic / عربي": "ar",  "🇬🇧 English": "en",  "🇫🇷 French": "fr",
    "🇪🇸 Spanish": "es",        "🇩🇪 German": "de",   "🇹🇷 Turkish": "tr",
    "🇮🇹 Italian": "it",        "🇨🇳 Chinese": "zh-CN","🇷🇺 Russian": "ru",
    "🇯🇵 Japanese": "ja",       "🇧🇷 Portuguese": "pt","🇮🇳 Hindi": "hi",
    "🇰🇷 Korean": "ko",         "🇳🇱 Dutch": "nl",    "🇵🇱 Polish": "pl",
    "🇸🇪 Swedish": "sv",        "🇬🇷 Greek": "el",    "🇹🇭 Thai": "th",
    "🇻🇳 Vietnamese": "vi",     "🇺🇦 Ukrainian": "uk", "🇮🇩 Indonesian": "id",
}

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "page":        "home",
    "role":        None,       # "speaker" | "audience"
    "room_code":   None,       # 4-digit string
    "last_hash":   None,
    "last_txt":    "",
    "last_lang":   "",
    "spk_lang":    "en",
    "aud_lang":    "ar",
    "aud_fpx":     24,
    "aud_rate":    3,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# URL param routing (deep-links still work)
_pg = st.query_params.get("page", "home")
if _pg in ("speaker", "audience", "home"):
    st.session_state.page = _pg


# ═════════════════════════════════════════════════════════════════════════════
#  H O M E  — pure Streamlit, zero iframe, no gap problem
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    # Brand header — single iframe, tight height
    components.html(PALETTE + FLAG_BAR + """
<style>
body{
  display:flex;flex-direction:column;align-items:center;
  justify-content:center;padding:28px 16px 16px;text-align:center;
}
.b-live{
  display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(52px,14vw,96px);line-height:.82;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--rl) 0%,var(--melon) 55%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.b-trans{
  display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(52px,14vw,96px);line-height:.82;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--gl) 0%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.b-sub{font-size:11px;color:#333;letter-spacing:.18em;text-transform:uppercase;margin-top:10px;}
.flag{display:flex;height:2px;width:100%;max-width:320px;
  border-radius:2px;overflow:hidden;margin:14px auto 0;}
.f1{flex:1;background:#1e1e1e;}.f2{flex:1;background:#2a2a2a;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}
</style>
<span class="b-live">LIVE</span>
<span class="b-trans">TRANSLATE</span>
<div class="b-sub">Real-time multilingual subtitles &nbsp;🇵🇸</div>
<div class="flag"><div class="f1"></div><div class="f2"></div>
  <div class="f3"></div><div class="f4"></div></div>
""", height=220, scrolling=False)

    # Role cards — pure Streamlit columns, no iframe, no gap
    st.markdown("""
<style>
/* Speaker card button */
div[data-testid="column"]:first-child .stButton>button{
  background:rgba(206,17,38,.10)!important;
  border:1px solid rgba(206,17,38,.3)!important;
  color:#ff3348!important;
  font-size:15px!important;
  padding:28px 8px!important;
  border-radius:18px!important;
  width:100%;min-height:140px;
  line-height:1.5!important;
}
div[data-testid="column"]:first-child .stButton>button:hover{
  background:rgba(206,17,38,.18)!important;
  box-shadow:0 12px 40px rgba(206,17,38,.2)!important;
}
/* Audience card button */
div[data-testid="column"]:last-child .stButton>button{
  background:rgba(0,122,61,.10)!important;
  border:1px solid rgba(0,122,61,.3)!important;
  color:#00c65e!important;
  font-size:15px!important;
  padding:28px 8px!important;
  border-radius:18px!important;
  width:100%;min-height:140px;
  line-height:1.5!important;
}
div[data-testid="column"]:last-child .stButton>button:hover{
  background:rgba(0,122,61,.18)!important;
  box-shadow:0 12px 40px rgba(0,122,61,.2)!important;
}
</style>
""", unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        if st.button(
            "🎤\n\nSPEAKER\n\nCreate a room & broadcast",
            use_container_width=True,
            key="h_spk"
        ):
            st.session_state.page = "speaker_setup"
            st.rerun()
    with c2:
        if st.button(
            "👥\n\nAUDIENCE\n\nJoin a room & read subs",
            use_container_width=True,
            key="h_aud"
        ):
            st.session_state.page = "audience_join"
            st.rerun()

    st.markdown("""
<div style='text-align:center;font-size:9px;color:#1e1e1e;letter-spacing:.08em;
  padding:18px 0 8px;font-family:monospace;'>
  faster-whisper &nbsp;·&nbsp; deep-translator &nbsp;·&nbsp; 100% free 🇵🇸
</div>""", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════════════════════
#  S P E A K E R  S E T U P  — generate room code
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker_setup":

    # Generate a code if we don't have one yet
    if not st.session_state.room_code:
        code = gen_code()
        room_create(code)
        st.session_state.room_code = code

    code = st.session_state.room_code

    # Header
    components.html(PALETTE + FLAG_BAR + """
<style>
body{padding:24px 16px 12px;}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(40px,9vw,76px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--melon) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:8px;}
</style>
<div class="title">YOUR ROOM</div>
<div class="sub">Share this code with your audience</div>
""", height=110, scrolling=False)

    # Room code display — big and bold
    components.html(PALETTE + f"""
<style>
body{{
  display:flex;flex-direction:column;align-items:center;
  padding:20px 16px 16px;text-align:center;
}}
.lbl{{font-size:10px;color:#333;letter-spacing:.18em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:12px;}}
.code-box{{
  background:#101010;border:2px solid rgba(253,107,75,.4);border-radius:20px;
  padding:28px 48px;position:relative;
}}
.code{{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(72px,20vw,120px);
  letter-spacing:14px;line-height:1;
  background:linear-gradient(135deg,var(--rl) 0%,var(--ml) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.hint{{font-size:11px;color:#2a2a2a;margin-top:12px;font-family:'JetBrains Mono',monospace;}}
</style>
<div class="lbl">🔑 Room Code</div>
<div class="code-box">
  <div class="code">{code}</div>
  <div class="hint">Tell your audience to enter this code</div>
</div>
""", height=220, scrolling=False)

    # Buttons: Enter Room / New Code / Back
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🎤 Enter Room & Speak", use_container_width=True, key="spk_enter"):
            st.session_state.page = "speaker"
            st.rerun()
    with b2:
        if st.button("🔄 New Code", use_container_width=True, key="spk_newcode"):
            new_code = gen_code()
            room_create(new_code)
            st.session_state.room_code = new_code
            st.rerun()

    if st.button("← Back to Home", use_container_width=True, key="spk_setup_home"):
        st.session_state.page = "home"
        st.session_state.room_code = None
        st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  A U D I E N C E  J O I N  — enter room code
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience_join":

    # Header
    components.html(PALETTE + FLAG_BAR + """
<style>
body{padding:24px 16px 12px;}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(40px,9vw,76px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--gl) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:8px;}
</style>
<div class="title">JOIN ROOM</div>
<div class="sub">Enter the 4-digit code from the speaker</div>
""", height=110, scrolling=False)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Code input — styled large
    code_input = st.text_input(
        "ROOM CODE",
        max_chars=4,
        placeholder="0000",
        key="aud_code_input",
        label_visibility="visible",
    )

    # Error state
    if "aud_join_error" not in st.session_state:
        st.session_state.aud_join_error = ""

    if st.session_state.aud_join_error:
        st.markdown(f"""
<div style='background:rgba(206,17,38,.1);border:1px solid rgba(206,17,38,.3);
  border-radius:10px;padding:12px 16px;text-align:center;font-size:13px;
  color:#ff3348;margin:8px 0;'>
  ❌ &nbsp; {st.session_state.aud_join_error}
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    j1, j2 = st.columns(2)
    with j1:
        if st.button("👥 Join Room", use_container_width=True, key="aud_join_btn"):
            code = (code_input or "").strip()
            if len(code) != 4 or not code.isdigit():
                st.session_state.aud_join_error = "Please enter a 4-digit code"
                st.rerun()
            elif not room_exists(code):
                st.session_state.aud_join_error = f"Room {code} not found. Check the code."
                st.rerun()
            else:
                st.session_state.aud_join_error = ""
                st.session_state.room_code = code
                st.session_state.page = "audience"
                st.rerun()
    with j2:
        if st.button("← Back to Home", use_container_width=True, key="aud_join_home"):
            st.session_state.aud_join_error = ""
            st.session_state.page = "home"
            st.rerun()

    # Visual hint
    components.html(PALETTE + """
<style>
body{padding:20px 16px;text-align:center;}
.box{background:#101010;border:1px solid #1a1a1a;border-radius:14px;padding:18px 16px;}
.icon{font-size:32px;margin-bottom:8px;}
.t{font-size:13px;color:#2a2a2a;line-height:1.6;}
.t b{color:#333;}
</style>
<div class="box">
  <div class="icon">💡</div>
  <div class="t">
    Ask the <b>Speaker</b> for the 4-digit room code.<br>
    Each session has its own private space.<br>
    You will only see that room's subtitles.
  </div>
</div>
""", height=140, scrolling=False)


# ═════════════════════════════════════════════════════════════════════════════
#  S P E A K E R  — broadcast page (requires room_code)
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    # Guard: must have a room code
    if not st.session_state.room_code:
        st.session_state.page = "speaker_setup"
        st.rerun()

    room = st.session_state.room_code

    # ── Top nav ───────────────────────────────────────────────────────────────
    nav_l, nav_r = st.columns([3, 1])
    with nav_l:
        components.html(PALETTE + FLAG_BAR + f"""
<style>
body{{padding:20px 16px 0;}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(40px,9vw,76px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--melon) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}}
.room-badge{{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(253,107,75,.1);border:1px solid rgba(253,107,75,.25);
  border-radius:8px;padding:4px 10px;margin-top:8px;
  font-size:12px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">SPEAK NOW</div>
<div class="sub">Choose language · Tap mic · Broadcast</div>
<div class="room-badge">🔑 Room {room}</div>
""", height=130, scrolling=False)
    with nav_r:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("← Home", use_container_width=True, key="spk_home"):
            st.session_state.page = "home"
            st.session_state.room_code = None
            st.rerun()

    # ── Language selector ─────────────────────────────────────────────────────
    spk_label = st.selectbox(
        "Your speaking language",
        list(SPEAKER_LANGS.keys()),
        index=list(SPEAKER_LANGS.values()).index(
            st.session_state.get("spk_lang", "en")
        ),
        key="spk_lang_sel",
    )
    st.session_state.spk_lang = SPEAKER_LANGS[spk_label]

    # ── Divider ───────────────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>body{padding:4px 0 2px;}</style>
<div style='height:1px;background:linear-gradient(90deg,
  rgba(0,122,61,.3),rgba(206,17,38,.3));border-radius:1px;'></div>
""", height=10, scrolling=False)

    # ── Mic recorder ─────────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{padding:8px 0 4px;}
.hint{font-size:11px;color:#2e2e2e;letter-spacing:.1em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;text-align:center;}
</style>
<div class="hint">🎙️ &nbsp; Tap the mic · speak · tap again to transcribe</div>
""", height=28, scrolling=False)

    rec = st.audio_input("Record", key="mic_input", label_visibility="collapsed")

    if rec:
        audio_bytes = rec.read()
        h = hash(audio_bytes)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            lang_code = st.session_state.spk_lang
            with st.spinner(f"Transcribing {spk_label}…"):
                txt, lang = transcribe(audio_bytes, lang_code)
            if txt:
                if db_save(room, txt, lang):
                    st.session_state.last_txt  = txt
                    st.session_state.last_lang = lang
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to save — please try again.")
            else:
                st.warning("⚠️ No speech detected — speak louder or closer to the mic.")

    # ── Status bar + Clear ────────────────────────────────────────────────────
    n = db_count(room)
    sc1, sc2 = st.columns([4, 1])
    with sc1:
        components.html(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
body{{margin:0;padding:3px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:8px;
  padding:9px 14px;background:#101010;border:1px solid #1e1e1e;
  border-radius:9px;font-size:12px;font-family:monospace;'>
  <span style='width:8px;height:8px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.18);display:inline-block;
    animation:dp 1.4s infinite;flex-shrink:0;'></span>
  <span style='color:#f2ede3;'><b>{n}</b> seg(s) &nbsp;·&nbsp;
    Lang: <b>{st.session_state.spk_lang.upper()}</b> &nbsp;·&nbsp;
    Room: <b>{room}</b></span>
</div>""", height=46, scrolling=False)
    with sc2:
        if st.button("🗑️ Clear", use_container_width=True, key="clr"):
            db_clear(room)
            st.cache_data.clear()
            st.session_state.last_txt = ""
            st.rerun()

    # ── Broadcast history ─────────────────────────────────────────────────────
    rows = db_all(room, 60)
    if not rows:
        components.html(PALETTE + """
<style>body{padding:28px 0;text-align:center;}</style>
<div style='font-size:40px;margin-bottom:10px;'>🎙️</div>
<div style='font-size:14px;color:#2a2a2a;'>
  Nothing broadcast yet — tap the mic above</div>""", height=100)
    else:
        cards = ""
        for i, (txt, lang, ts) in enumerate(rows):
            is_new = (i == 0)
            border = "border-left:3px solid #fd6b4b;" if is_new else ""
            bg     = "background:linear-gradient(135deg,rgba(253,107,75,.05),#161616 60%);" if is_new else ""
            anim   = "animation:slid .35s ease;" if is_new else ""
            ntag   = '<span class="ntag">NEW</span>' if is_new else ""
            cards += f"""
<div class="hc" style="{border}{bg}{anim}">
  <div class="meta">
    <span class="ts">🕐 {ts}</span>
    <span class="ltag">{lang.upper()}</span>{ntag}
  </div>
  <div class="htxt">{txt}</div>
</div>"""

        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 24px;}}
@keyframes slid{{from{{opacity:.1;transform:translateY(-6px)}}to{{opacity:1;transform:none}}}}
.hc{{background:#141414;border:1px solid #1e1e1e;border-radius:12px;
  padding:14px 16px;margin:6px 0;transition:border-color .2s;}}
.hc:hover{{border-color:#2e2e2e;}}
.meta{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:8px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#2e2e2e;}}
.ltag{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);
  border-radius:4px;padding:1px 7px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ntag{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);
  border-radius:4px;padding:1px 7px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.htxt{{font-size:16px;font-weight:600;color:#f2ede3;line-height:1.55;direction:auto;}}
</style>
{cards}
""", height=min(80 + len(rows) * 88, 2400), scrolling=True)


# ═════════════════════════════════════════════════════════════════════════════
#  A U D I E N C E  — live subtitles for their specific room
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    # Guard: must be in a room
    if not st.session_state.room_code:
        st.session_state.page = "audience_join"
        st.rerun()

    room = st.session_state.room_code

    # ── Top nav ───────────────────────────────────────────────────────────────
    anl, anr = st.columns([3, 1])
    with anl:
        components.html(PALETTE + FLAG_BAR + f"""
<style>
body{{padding:20px 16px 0;}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(40px,9vw,76px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--gl) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}}
.room-badge{{
  display:inline-flex;align-items:center;gap:6px;
  background:rgba(0,122,61,.1);border:1px solid rgba(0,122,61,.25);
  border-radius:8px;padding:4px 10px;margin-top:8px;
  font-size:12px;color:#00c65e;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">LIVE SUBS</div>
<div class="sub">Real-time translated subtitles</div>
<div class="room-badge">🔑 Room {room}</div>
""", height=130, scrolling=False)
    with anr:
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        if st.button("← Home", use_container_width=True, key="aud_home"):
            st.session_state.page = "home"
            st.session_state.room_code = None
            st.rerun()

    # ── Controls ──────────────────────────────────────────────────────────────
    cc1, cc2 = st.columns([3, 1])
    with cc1:
        lc_sel = st.selectbox(
            "Language",
            list(AUDIENCE_LANGS.keys()),
            index=list(AUDIENCE_LANGS.values()).index(
                st.session_state.get("aud_lang", "ar")
            ),
            label_visibility="collapsed",
            key="aud_lang_sel",
        )
        st.session_state.aud_lang = AUDIENCE_LANGS[lc_sel]
    with cc2:
        rate = st.selectbox(
            "Refresh",
            [2, 3, 5, 8],
            index=1,
            format_func=lambda x: f"↺ {x}s",
            label_visibility="collapsed",
            key="aud_rate_sel",
        )
        st.session_state.aud_rate = rate

    # Font size buttons
    fc1, fc2, fc3 = st.columns([1, 2, 1])
    with fc1:
        if st.button("A−", use_container_width=True, key="fdn"):
            st.session_state.aud_fpx = max(16, st.session_state.aud_fpx - 4)
    with fc2:
        fpx = st.session_state.aud_fpx
        components.html(f"""<style>body{{margin:0;padding:0;background:transparent;text-align:center;}}</style>
<div style='font-size:12px;color:#333;font-family:monospace;padding:8px 0;'>
  font: <b style='color:#888;'>{fpx}px</b></div>""", height=34, scrolling=False)
    with fc3:
        if st.button("A+", use_container_width=True, key="fup"):
            st.session_state.aud_fpx = min(64, st.session_state.aud_fpx + 4)

    # Wake Lock — keeps phone screen on
    components.html("""
<script>
(async function(){
  if('wakeLock' in navigator){
    try{await navigator.wakeLock.request('screen');}catch(e){}
    document.addEventListener('visibilitychange',async()=>{
      if(document.visibilityState==='visible'){
        try{await navigator.wakeLock.request('screen');}catch(e){}
      }
    });
  }
})();
</script>
""", height=0, scrolling=False)

    # ── Live subtitle display — auto-refreshing fragment ─────────────────────
    tgt  = st.session_state.aud_lang
    fpx  = st.session_state.aud_fpx
    rate = st.session_state.aud_rate

    @st.fragment(run_every=rate)
    def live_display():
        tgt  = st.session_state.aud_lang
        fpx  = st.session_state.aud_fpx
        rows = db_all(room, 25)
        n    = db_count(room)

        # Status dot
        components.html(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
body{{margin:0;padding:2px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:7px;
  padding:8px 12px;background:#0d0d0d;border:1px solid #1a1a1a;
  border-radius:8px;font-size:11px;font-family:monospace;'>
  <span style='width:7px;height:7px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.15);display:inline-block;
    animation:dp 1.4s infinite;flex-shrink:0;'></span>
  <span style='color:#f2ede3;'>🔴 Live &nbsp;·&nbsp; <b>{n}</b> segs &nbsp;·&nbsp;
    Room <b>{room}</b> &nbsp;·&nbsp; <b>{tgt.upper()}</b> &nbsp;·&nbsp; ↺{rate}s</span>
</div>""", height=40, scrolling=False)

        if not rows:
            components.html(PALETTE + """
<style>body{padding:30px 0;text-align:center;}</style>
<div style='font-size:44px;margin-bottom:10px'>⏳</div>
<div style='font-size:15px;color:#2a2a2a;'>Waiting for speaker…</div>
<div style='font-size:11px;color:#1a1a1a;margin-top:6px;'>
  The speaker will broadcast to this room</div>""", height=160)
            return

        # Latest — BIG
        ltxt, llang, lts = rows[0]
        # Perfect translation: always pass known source language explicitly
        ltranslated = tr(ltxt, tgt, llang)
        tb = tgt.split("-")[0].lower()
        sb = (llang or "").split("-")[0].lower()
        show_src = (sb != tb) and ltxt != ltranslated
        src_div  = f'<div class="so">{llang.upper()}: {ltxt}</div>' if show_src else ""

        components.html(PALETTE + f"""
<style>
body{{padding:6px 0 4px;}}
.stage{{
  background:#0a0a0a;border:1px solid #1a1a1a;border-radius:16px;
  padding:24px 20px;position:relative;overflow:hidden;
  display:flex;flex-direction:column;justify-content:center;min-height:120px;
}}
.stage::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--red) 0%,#0a0a0a 35%,var(--green) 100%);}}
.so{{font-size:12px;color:#2a2a2a;font-style:italic;direction:auto;
  margin-bottom:10px;padding-bottom:10px;border-bottom:1px solid #181818;}}
.st{{color:var(--white);font-weight:700;line-height:1.4;direction:auto;
  font-size:{fpx}px;animation:fi .4s ease;}}
@keyframes fi{{from{{opacity:.1;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.sm{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#1e1e1e;margin-top:12px;}}
</style>
<div class="stage">
  {src_div}
  <div class="st">{ltranslated}</div>
  <div class="sm">🕐 {lts} &nbsp;·&nbsp; {(llang or "?").upper()} → {tgt.upper()}</div>
</div>
""", height=max(180, fpx * 3 + 80), scrolling=False)

        # Action row — Read aloud / Copy / Fullscreen
        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 6px;}}
.row{{display:flex;gap:8px;flex-wrap:wrap;}}
.btn{{
  flex:1;min-width:80px;background:#141414;border:1px solid #1e1e1e;border-radius:10px;
  padding:12px 8px;color:#444;font-size:12px;cursor:pointer;
  transition:all .15s;font-family:'Cairo',sans-serif;font-weight:700;
  text-align:center;-webkit-tap-highlight-color:transparent;
}}
.btn:active{{background:#1e1e1e;color:#f2ede3;transform:scale(.96);}}
.btn:hover{{background:#1e1e1e;color:#f2ede3;border-color:#2e2e2e;}}
#cm{{color:#00c65e;font-size:11px;opacity:0;transition:opacity .3s;align-self:center;}}
#fs{{display:none;position:fixed;inset:0;background:#000;z-index:99999;
  align-items:center;justify-content:center;cursor:pointer;
  flex-direction:column;text-align:center;padding:32px;}}
#fs-t{{color:#f2ede3;font-weight:700;direction:auto;line-height:1.35;
  font-size:clamp(28px,8vw,80px);max-width:95%;}}
#fs-b{{position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#000 30%,#007a3d 100%);}}
#fs-h{{position:absolute;bottom:18px;font-size:11px;color:#1a1a1a;font-family:monospace;}}
</style>
<div class="row">
  <button class="btn" onclick="speak()">🔊 Aloud</button>
  <button class="btn" onclick="copy()">📋 Copy</button>
  <button class="btn" onclick="openfs()">⛶ Full</button>
  <span id="cm">✓ Copied</span>
</div>
<div id="fs" onclick="closefs()">
  <div id="fs-t">{ltranslated}</div>
  <div id="fs-h">Tap anywhere to close</div>
  <div id="fs-b"></div>
</div>
<script>
const T={repr(ltranslated)},L="{tgt}";
function speak(){{
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(T);u.lang=L;speechSynthesis.speak(u);
}}
function copy(){{
  navigator.clipboard.writeText(T).then(()=>{{
    const m=document.getElementById('cm');
    m.style.opacity='1';
    setTimeout(()=>m.style.opacity='0',2000);
  }}).catch(()=>{{}});
  if(navigator.vibrate) navigator.vibrate(40);
}}
function openfs(){{document.getElementById('fs').style.display='flex';}}
function closefs(){{document.getElementById('fs').style.display='none';}}
</script>
""", height=60, scrolling=False)

        # ── Older segments ─────────────────────────────────────────────────────
        older = rows[1:]
        if older:
            components.html("""<style>body{margin:0;padding:0;background:transparent;}</style>
<div style='margin:4px 0 3px;font-size:10px;color:#1a1a1a;
  font-family:monospace;letter-spacing:.1em;'>
  ─── PREVIOUS ───</div>""", height=22, scrolling=False)

            h_html = ""
            tb = tgt.split("-")[0].lower()
            for st_txt, sl, sts in older:
                s_tr  = tr(st_txt, tgt, sl)          # explicit source language
                sb2   = (sl or "").split("-")[0].lower()
                so_d  = f'<div class="ao">{sl.upper()}: {st_txt}</div>' \
                        if (sb2 != tb and st_txt != s_tr) else ""
                h_html += f"""
<div class="ac">
  {so_d}
  <div class="at">{s_tr}</div>
  <div class="ats">🕐 {sts}</div>
</div>"""

            components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:2px 0 20px;}}
.ac{{background:#111;border:1px solid #1a1a1a;border-radius:10px;
  padding:12px 14px;margin:5px 0;opacity:.5;transition:opacity .2s;}}
.ac:hover{{opacity:.8;}}
.ao{{font-size:11px;color:#222;font-style:italic;direction:auto;margin-bottom:4px;}}
.at{{font-size:15px;font-weight:600;color:#666;direction:auto;line-height:1.45;}}
.ats{{font-size:10px;color:#1a1a1a;font-family:'JetBrains Mono',monospace;margin-top:4px;}}
</style>
{h_html}
""", height=min(50 + len(older) * 86, 1800), scrolling=True)

    live_display()
