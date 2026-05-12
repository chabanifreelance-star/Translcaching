"""
LiveTranslate — v10  (Quick lang buttons · Duration check · History fix · RTL perfect)
================================================================================
requirements.txt:
  streamlit>=1.37
  faster-whisper
  deep-translator
  numpy

Run:
  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import sqlite3, os, tempfile, random, string, html, re, time
from datetime import datetime

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ═══════════════════════════════════════════════════════════════════════════════
# SECURITY HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def esc(text: str) -> str:
    """HTML-escape any user-supplied string before injecting into HTML."""
    return html.escape(str(text), quote=True)

RTL_LANGS = {"ar", "he", "fa", "ur", "yi", "ps", "ku", "dv", "ug", "ckb"}

def dir_attr(lang_code: str) -> str:
    """Return the correct HTML dir attribute for a language code."""
    base = (lang_code or "").split("-")[0].lower()
    return "rtl" if base in RTL_LANGS else "ltr"

def rtl_style(lang_code: str) -> str:
    """Return inline CSS for direction + alignment based on language."""
    if dir_attr(lang_code) == "rtl":
        return "direction:rtl;text-align:right;unicode-bidi:embed;"
    return "direction:ltr;text-align:left;"

# Sanitize room code to digits only, exactly 4 chars
def sanitize_code(raw: str) -> str:
    return re.sub(r"[^0-9]", "", (raw or ""))[:4]

# ── global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
#MainMenu,header,footer,
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stStatusWidget"]{display:none!important;}

.stApp{background:#080808!important;}
.block-container{padding:0!important;max-width:100%!important;}
body,html{overflow-x:hidden!important;}

/* ── uniform button reset ── */
.stButton>button{
  background:#161616!important;
  border:1px solid #2a2a2a!important;
  color:#f2ede3!important;
  border-radius:12px!important;
  font-weight:700!important;
  font-size:13px!important;
  padding:11px 8px!important;
  width:100%!important;
  transition:background .15s,border-color .15s!important;
}
.stButton>button:hover{
  background:#1e1e1e!important;
  border-color:#3a3a3a!important;
}
.stButton>button:active{
  background:#252525!important;
}

/* ── text input (room code) ── */
.stTextInput>div>div>input{
  background:#161616!important;
  border:1px solid #2a2a2a!important;
  color:#f2ede3!important;
  border-radius:12px!important;
  font-size:22px!important;
  text-align:center!important;
  letter-spacing:8px!important;
  font-weight:700!important;
  font-family:monospace!important;
  padding:14px!important;
}
.stTextInput label{
  color:#555!important;
  font-size:11px!important;
  letter-spacing:.1em!important;
  text-transform:uppercase!important;
}

/* ── remove iframe margin ── */
iframe{display:block!important;}
div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;}
</style>
""", unsafe_allow_html=True)

# ── shared iframe CSS ─────────────────────────────────────────────────────────
PALETTE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=Noto+Naskh+Arabic:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
:root{
  --bg:#080808;--card:#161616;--b:#222;--b2:#2e2e2e;
  --white:#f2ede3;--dim:#2a2a2a;
  --green:#007a3d;--gl:#00c65e;
  --red:#ce1126;--rl:#ff3348;
  --melon:#fd6b4b;--ml:#ff8a6a;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{
  background:transparent;color:var(--white);
  font-family:'Cairo','Noto Naskh Arabic',sans-serif;
  -webkit-font-smoothing:antialiased;
  overflow-x:hidden;
}
/* Global RTL text class */
.rtl-text{
  direction:rtl;
  text-align:right;
  unicode-bidi:embed;
  font-family:'Noto Naskh Arabic','Cairo',sans-serif;
  font-feature-settings:"kern" 1,"liga" 1,"calt" 1;
}
.ltr-text{
  direction:ltr;
  text-align:left;
  unicode-bidi:embed;
  font-family:'Cairo',sans-serif;
}
</style>
"""

# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
DB = os.path.join(tempfile.gettempdir(), "lt_v9.db")

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    with _cx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS rooms(
            code    TEXT PRIMARY KEY,
            created TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS seg(
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            txt  TEXT NOT NULL,
            lang TEXT DEFAULT '',
            ts   TEXT NOT NULL
        )""")
        # Rate-limit table: track save timestamps per room
        c.execute("""CREATE TABLE IF NOT EXISTS rate_limit(
            room TEXT PRIMARY KEY,
            last_save REAL NOT NULL,
            count INTEGER DEFAULT 0
        )""")
        c.commit()

def room_create(code):
    with _cx() as c:
        c.execute("INSERT OR IGNORE INTO rooms(code,created) VALUES(?,?)",
                  (code, datetime.now().strftime("%H:%M")))
        c.commit()

def room_exists(code):
    # Only check sanitized numeric codes
    if not re.fullmatch(r"[0-9]{4}", code or ""):
        return False
    with _cx() as c:
        return c.execute(
            "SELECT 1 FROM rooms WHERE code=?", (code,)
        ).fetchone() is not None

def _check_rate_limit(room: str, max_per_minute: int = 30) -> bool:
    """Return True if save is allowed, False if rate-limited."""
    now = time.time()
    with _cx() as c:
        row = c.execute(
            "SELECT last_save, count FROM rate_limit WHERE room=?", (room,)
        ).fetchone()
        if row is None:
            c.execute(
                "INSERT INTO rate_limit(room,last_save,count) VALUES(?,?,1)",
                (room, now)
            )
            c.commit()
            return True
        last_save, count = row
        # Reset window every 60 s
        if now - last_save > 60:
            c.execute(
                "UPDATE rate_limit SET last_save=?, count=1 WHERE room=?",
                (now, room)
            )
            c.commit()
            return True
        if count >= max_per_minute:
            return False
        c.execute(
            "UPDATE rate_limit SET count=count+1 WHERE room=?", (room,)
        )
        c.commit()
        return True

def db_save(room, txt, lang):
    try:
        # Rate-limit check
        if not _check_rate_limit(room):
            return False
        # Sanitize: strip leading/trailing whitespace, limit length
        clean = txt.strip()[:2000]
        if not clean:
            return False
        with _cx() as c:
            c.execute(
                "INSERT INTO seg(room,txt,lang,ts) VALUES(?,?,?,?)",
                (room, clean, lang, datetime.now().strftime("%H:%M"))
            )
            c.commit()
        return True
    except Exception:
        return False

def db_all(room, limit=40):
    try:
        if not re.fullmatch(r"[0-9]{4}", room or ""):
            return []
        with _cx() as c:
            return c.execute(
                "SELECT txt,lang,ts FROM seg WHERE room=? ORDER BY id DESC LIMIT ?",
                (room, limit)
            ).fetchall()
    except Exception:
        return []

def db_count(room):
    try:
        if not re.fullmatch(r"[0-9]{4}", room or ""):
            return 0
        with _cx() as c:
            return c.execute(
                "SELECT COUNT(*) FROM seg WHERE room=?", (room,)
            ).fetchone()[0]
    except Exception:
        return 0

def db_clear(room):
    if not re.fullmatch(r"[0-9]{4}", room or ""):
        return
    with _cx() as c:
        c.execute("DELETE FROM seg WHERE room=?", (room,))
        c.commit()

def gen_code():
    return "".join(random.choices(string.digits, k=4))

init_db()

# ═══════════════════════════════════════════════════════════════════════════════
# WHISPER
# ═══════════════════════════════════════════════════════════════════════════════
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

def transcribe(audio_bytes, lang_code):
    model = get_whisper()
    if not model:
        return "", lang_code
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes); tmp = f.name
        segs, _ = model.transcribe(
            tmp, task="transcribe", language=lang_code,
            beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        return " ".join(s.text.strip() for s in segs).strip(), lang_code
    except Exception:
        return "", lang_code
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass

# ═══════════════════════════════════════════════════════════════════════════════
# TRANSLATION  — perfect Arabic support, always explicit source
# ═══════════════════════════════════════════════════════════════════════════════

# Map of language codes to Google Translate accepted codes
_LANG_MAP = {
    "zh-cn": "zh-CN",
    "zh-tw": "zh-TW",
    "ar":    "ar",
    "he":    "iw",       # Google uses 'iw' for Hebrew
}

def _norm_for_google(code: str) -> str:
    """Normalize a language code for Google Translate."""
    c = (code or "").strip()
    low = c.lower()
    if low in _LANG_MAP:
        return _LANG_MAP[low]
    if low.startswith("zh"):
        return c  # preserve zh-CN / zh-TW casing
    return low.split("-")[0]

# NOTE: Do NOT cache tr() with @st.cache_data — it can cross-contaminate
# results between different target languages for the same source text.
# We use a simple in-process dict cache instead (safe, same process).
_TR_CACHE: dict = {}
_TR_CACHE_MAX = 2000  # evict oldest when full

def tr(text: str, target: str, source: str) -> str:
    """Translate text from source to target language.
    Returns original text on failure or if already in target language."""
    if not text or not text.strip():
        return text

    src = _norm_for_google(source)
    tgt = _norm_for_google(target)

    if src == tgt:
        return text

    cache_key = (text[:200], src, tgt)
    if cache_key in _TR_CACHE:
        return _TR_CACHE[cache_key]

    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=src, target=tgt).translate(text)
        translated = result if result and result.strip() else text
    except Exception:
        translated = text

    # Evict oldest entries if cache is full
    if len(_TR_CACHE) >= _TR_CACHE_MAX:
        oldest = next(iter(_TR_CACHE))
        del _TR_CACHE[oldest]
    _TR_CACHE[cache_key] = translated
    return translated

# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGES
# ═══════════════════════════════════════════════════════════════════════════════
SPEAKER_LANGS = {
    "🇬🇧 English":   "en",
    "🇸🇦 Arabic":    "ar",
    "🇫🇷 French":    "fr",
    "🇹🇷 Turkish":   "tr",
    "🇪🇸 Spanish":   "es",
    "🇩🇪 German":    "de",
    "🇮🇹 Italian":   "it",
    "🇷🇺 Russian":   "ru",
}

AUDIENCE_LANGS = {
    "🇸🇦 Arabic":      "ar",  "🇬🇧 English":   "en",
    "🇫🇷 French":      "fr",  "🇪🇸 Spanish":   "es",
    "🇩🇪 German":      "de",  "🇹🇷 Turkish":   "tr",
    "🇮🇹 Italian":     "it",  "🇨🇳 Chinese":   "zh-CN",
    "🇷🇺 Russian":     "ru",  "🇯🇵 Japanese":  "ja",
    "🇧🇷 Portuguese":  "pt",  "🇮🇳 Hindi":     "hi",
    "🇰🇷 Korean":      "ko",  "🇳🇱 Dutch":     "nl",
    "🇵🇱 Polish":      "pl",  "🇸🇪 Swedish":   "sv",
    "🇬🇷 Greek":       "el",  "🇹🇭 Thai":      "th",
    "🇻🇳 Vietnamese":  "vi",  "🇺🇦 Ukrainian": "uk",
    "🇮🇩 Indonesian":  "id",
}

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════════════════════
DEFAULTS = {
    "page":       "home",
    "room_code":  None,
    "last_hash":  None,
    "last_txt":   "",
    "last_lang":  "",
    "spk_lang":   "en",
    "aud_lang":   "ar",
    "aud_fpx":    28,
    "aud_rate":   3,
    "join_error": "",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(page, **kw):
    st.session_state.page = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
#  H O M E
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    components.html(PALETTE + """
<style>
body{
  display:flex;flex-direction:column;align-items:center;
  padding:30px 16px 18px;text-align:center;background:transparent;
}
.live{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(56px,15vw,104px);line-height:.80;letter-spacing:.04em;
  background:linear-gradient(135deg,#ff3348 0%,#fd6b4b 55%,#f2ede3 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.trans{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(56px,15vw,104px);line-height:.80;letter-spacing:.04em;
  background:linear-gradient(135deg,#00c65e 0%,#f2ede3 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.sub{font-size:11px;color:#2e2e2e;letter-spacing:.18em;text-transform:uppercase;margin-top:12px;}
.bar{
  display:flex;height:2px;width:90%;max-width:340px;
  border-radius:2px;overflow:hidden;margin:16px auto 0;
}
.b1{flex:1;background:#1e1e1e;}.b2{flex:1;background:#2a2a2a;}
.b3{flex:1;background:#007a3d;}.b4{flex:1;background:#ce1126;}
</style>
<div class="live">LIVE</div>
<div class="trans">TRANSLATE</div>
<div class="sub">Real-time multilingual subtitles 🇵🇸</div>
<div class="bar">
  <div class="b1"></div><div class="b2"></div>
  <div class="b3"></div><div class="b4"></div>
</div>
""", height=230, scrolling=False)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button("🎤  SPEAKER", key="btn_spk", use_container_width=True):
            go("speaker_setup")
    with col2:
        if st.button("👥  AUDIENCE", key="btn_aud", use_container_width=True):
            go("audience_join")

    st.markdown("""
<div style='text-align:center;font-size:9px;color:#1c1c1c;
  letter-spacing:.07em;padding:12px 0 4px;font-family:monospace;'>
  faster-whisper · deep-translator · 100% free 🇵🇸
</div>""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  S P E A K E R   S E T U P
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker_setup":

    if not st.session_state.room_code:
        code = gen_code()
        room_create(code)
        st.session_state.room_code = code

    code = st.session_state.room_code

    components.html(PALETTE + """
<style>
body{padding:22px 16px 8px;background:transparent;}
.title{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(42px,10vw,76px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:7px;}
</style>
<div class="title">YOUR ROOM</div>
<div class="sub">Share this code with your audience</div>
""", height=95, scrolling=False)

    components.html(PALETTE + f"""
<style>
body{{
  display:flex;flex-direction:column;align-items:center;
  padding:8px 16px 12px;text-align:center;background:transparent;
}}
.lbl{{
  font-size:10px;color:#333;letter-spacing:.18em;
  text-transform:uppercase;font-family:'JetBrains Mono',monospace;margin-bottom:10px;
}}
.box{{
  background:#0f0f0f;border:2px solid rgba(253,107,75,.35);
  border-radius:20px;padding:22px 36px 16px;
}}
.code{{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(80px,22vw,128px);
  letter-spacing:16px;line-height:1;
  background:linear-gradient(135deg,#ff3348,#ff8a6a);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.hint{{font-size:11px;color:#2a2a2a;margin-top:7px;font-family:'JetBrains Mono',monospace;}}
</style>
<div class="lbl">🔑 Room Code</div>
<div class="box">
  <div class="code">{esc(code)}</div>
  <div class="hint">Tell your audience to enter this code</div>
</div>
""", height=205, scrolling=False)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button("🎤  Enter Room & Speak", key="spk_enter", use_container_width=True):
            go("speaker")
    with c2:
        if st.button("🔄  New Code", key="spk_newcode", use_container_width=True):
            c = gen_code()
            room_create(c)
            st.session_state.room_code = c
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("← Back to Home", key="spk_setup_back", use_container_width=True):
        go("home", room_code=None)


# ═══════════════════════════════════════════════════════════════════════════════
#  A U D I E N C E   J O I N
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience_join":

    components.html(PALETTE + """
<style>
body{padding:22px 16px 8px;background:transparent;}
.title{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(42px,10vw,76px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:7px;}
</style>
<div class="title">JOIN ROOM</div>
<div class="sub">Enter the 4-digit code from the speaker</div>
""", height=95, scrolling=False)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    code_input = st.text_input(
        "ROOM CODE",
        max_chars=4,
        placeholder="1234",
        key="aud_code_field",
    )

    if st.session_state.join_error:
        st.markdown(f"""
<div style='background:rgba(206,17,38,.1);border:1px solid rgba(255,51,72,.3);
  border-radius:10px;padding:11px 14px;font-size:13px;color:#ff3348;
  text-align:center;margin:6px 0;'>
  ❌ {esc(st.session_state.join_error)}
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    j1, j2 = st.columns(2, gap="small")
    with j1:
        if st.button("👥  Join Room", key="aud_join_btn", use_container_width=True):
            code = sanitize_code(code_input)
            if len(code) != 4:
                st.session_state.join_error = "Please enter a valid 4-digit code"
                st.rerun()
            elif not room_exists(code):
                st.session_state.join_error = f"Room {code} not found — check the code"
                st.rerun()
            else:
                st.session_state.join_error = ""
                go("audience", room_code=code)
    with j2:
        if st.button("← Back", key="aud_join_back", use_container_width=True):
            st.session_state.join_error = ""
            go("home")

    components.html(PALETTE + """
<style>
body{padding:16px 0;background:transparent;}
.tip{
  background:#0f0f0f;border:1px solid #1a1a1a;
  border-radius:14px;padding:16px 14px;text-align:center;
}
.icon{font-size:28px;margin-bottom:7px;}
.t{font-size:12px;color:#2a2a2a;line-height:1.65;}
.t b{color:#333;}
</style>
<div class="tip">
  <div class="icon">💡</div>
  <div class="t">
    Ask the <b>Speaker</b> for the 4-digit room code.<br>
    Each room is private — only that room's subtitles appear.
  </div>
</div>
""", height=125, scrolling=False)


# ═══════════════════════════════════════════════════════════════════════════════
#  S P E A K E R  — broadcast
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    if not st.session_state.room_code:
        go("speaker_setup")

    room = st.session_state.room_code

    nl, nr = st.columns([3, 1], gap="small")
    with nl:
        components.html(PALETTE + f"""
<style>
body{{padding:20px 16px 6px;background:transparent;}}
.title{{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(42px,10vw,76px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}}
.badge{{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(253,107,75,.1);border:1px solid rgba(253,107,75,.25);
  border-radius:7px;padding:3px 9px;margin-top:7px;
  font-size:11px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">SPEAK NOW</div>
<div class="sub">Tap mic · speak · tap again</div>
<div class="badge">🔑 Room {esc(room)}</div>
""", height=120, scrolling=False)
    with nr:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("← Home", key="spk_home", use_container_width=True):
            go("home", room_code=None)

    spk_label = st.selectbox(
        "Speaking language",
        list(SPEAKER_LANGS.keys()),
        index=list(SPEAKER_LANGS.values()).index(st.session_state.spk_lang),
        key="spk_lang_sel",
    )
    st.session_state.spk_lang = SPEAKER_LANGS[spk_label]

    st.markdown("""
<div style='height:1px;
  background:linear-gradient(90deg,rgba(0,122,61,.3),rgba(206,17,38,.3));
  margin:4px 0;'></div>""", unsafe_allow_html=True)

    st.markdown("""
<div style='font-size:11px;color:#2e2e2e;letter-spacing:.1em;text-transform:uppercase;
  font-family:monospace;text-align:center;padding:6px 0 2px;'>
  🎙️  tap mic · speak · tap again to transcribe
</div>""", unsafe_allow_html=True)

    rec = st.audio_input("mic", key="mic_input", label_visibility="collapsed")

    if rec:
        audio_bytes = rec.read()
        h = hash(audio_bytes)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            lang_code = st.session_state.spk_lang

            # ── Duration check (WAV header: sample_rate at offset 24, num_samples = (size-44)/channels/bits*8) ──
            _too_long = False
            try:
                import struct
                if len(audio_bytes) > 44 and audio_bytes[:4] == b'RIFF':
                    _sr   = struct.unpack_from('<I', audio_bytes, 24)[0]
                    _nchan = struct.unpack_from('<H', audio_bytes, 22)[0]
                    _bps  = struct.unpack_from('<H', audio_bytes, 34)[0]
                    _data_size = len(audio_bytes) - 44
                    _duration = _data_size / (_sr * _nchan * (_bps // 8)) if _sr and _nchan and _bps else 0
                    if _duration > 60:
                        _too_long = True
                        st.warning(
                            f"⚠️ Recording is too long ({int(_duration)}s). "
                            "Please keep each recording under 60 seconds for reliable transcription. "
                            "Split your speech into shorter segments."
                        )
            except Exception:
                pass

            if not _too_long:
                with st.spinner("Transcribing…"):
                    txt, lang = transcribe(audio_bytes, lang_code)
                if txt:
                    if db_save(room, txt, lang):
                        st.session_state.last_txt  = txt
                        st.session_state.last_lang = lang
                        st.rerun()
                    else:
                        st.error("Save failed — try again.")
                else:
                    st.warning("⚠️ No speech detected — try again.")

    n = db_count(room)
    s1, s2 = st.columns([4, 1], gap="small")
    with s1:
        components.html(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
body{{margin:0;padding:3px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:8px;padding:9px 13px;
  background:#101010;border:1px solid #1e1e1e;border-radius:9px;
  font-size:12px;font-family:monospace;'>
  <span style='width:8px;height:8px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.18);
    animation:dp 1.4s infinite;flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    <b>{n}</b> seg(s) · <b>{esc(st.session_state.spk_lang.upper())}</b> · Room <b>{esc(room)}</b>
  </span>
</div>""", height=46, scrolling=False)
    with s2:
        if st.button("🗑 Clear", key="clr_btn", use_container_width=True):
            db_clear(room)
            st.session_state.last_txt = ""
            st.rerun()

    rows = db_all(room, 60)
    if not rows:
        components.html(PALETTE + """
<style>body{padding:28px 0;text-align:center;background:transparent;}</style>
<div style='font-size:38px;margin-bottom:8px;'>🎙️</div>
<div style='font-size:13px;color:#2a2a2a;'>Nothing yet — tap the mic above</div>
""", height=90)
    else:
        cards = ""
        for i, (txt, lang, ts) in enumerate(rows):
            safe_txt = esc(txt)
            safe_lang = esc((lang or "??").upper())
            safe_ts = esc(ts)
            d = dir_attr(lang)
            rs = rtl_style(lang)
            new = i == 0
            bl = "border-left:3px solid #fd6b4b;" if new else ""
            bg = "background:linear-gradient(135deg,rgba(253,107,75,.05),#161616 55%);" if new else ""
            an = "animation:sl .35s ease;" if new else ""
            nt = '<span class="ntag">NEW</span>' if new else ""
            cards += f"""
<div class="hc" style="{bl}{bg}{an}">
  <div class="meta">
    <span class="ts">🕐 {safe_ts}</span>
    <span class="ltag">{safe_lang}</span>{nt}
  </div>
  <div class="htxt" dir="{d}" style="{rs}">{safe_txt}</div>
</div>"""
        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 24px;}}
@keyframes sl{{from{{opacity:.1;transform:translateY(-5px)}}to{{opacity:1;transform:none}}}}
.hc{{background:#141414;border:1px solid #1e1e1e;border-radius:12px;
  padding:13px 15px;margin:5px 0;}}
.meta{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:7px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#2e2e2e;}}
.ltag{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);
  border-radius:4px;padding:1px 7px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ntag{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);
  border-radius:4px;padding:1px 7px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.htxt{{font-size:16px;font-weight:600;color:#f2ede3;line-height:1.65;
  font-family:'Noto Naskh Arabic','Cairo',sans-serif;}}
</style>
{cards}
""", height=min(80 + len(rows) * 88, 2400), scrolling=True)


# ═══════════════════════════════════════════════════════════════════════════════
#  A U D I E N C E  — live subtitles
# ═══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    if not st.session_state.room_code:
        go("audience_join")

    room = st.session_state.room_code

    al, ar_ = st.columns([3, 1], gap="small")
    with al:
        components.html(PALETTE + f"""
<style>
body{{padding:20px 16px 6px;background:transparent;}}
.title{{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(42px,10vw,76px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}}
.badge{{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(0,122,61,.1);border:1px solid rgba(0,198,94,.25);
  border-radius:7px;padding:3px 9px;margin-top:7px;
  font-size:11px;color:#00c65e;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">LIVE SUBS</div>
<div class="sub">Real-time translated subtitles</div>
<div class="badge">🔑 Room {esc(room)}</div>
""", height=120, scrolling=False)
    with ar_:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button("← Home", key="aud_home", use_container_width=True):
            go("home", room_code=None)

    # ── Quick language buttons ─────────────────────────────────────────────
    q1, q2, q3, q4 = st.columns(4, gap="small")
    with q1:
        if st.button("🇬🇧 EN", key="ql_en", use_container_width=True):
            st.session_state.aud_lang = "en"; st.rerun()
    with q2:
        if st.button("🇫🇷 FR", key="ql_fr", use_container_width=True):
            st.session_state.aud_lang = "fr"; st.rerun()
    with q3:
        if st.button("🇸🇦 AR", key="ql_ar", use_container_width=True):
            st.session_state.aud_lang = "ar"; st.rerun()
    with q4:
        if st.button("🇹🇷 TR", key="ql_tr", use_container_width=True):
            st.session_state.aud_lang = "tr"; st.rerun()

    # Active lang indicator bar
    _ql_labels = {"en": "🇬🇧 EN", "fr": "🇫🇷 FR", "ar": "🇸🇦 AR", "tr": "🇹🇷 TR"}
    _ql_active_label = _ql_labels.get(st.session_state.aud_lang, "")
    if _ql_active_label:
        components.html(f"""
<style>body{{margin:0;padding:0 0 2px;background:transparent;}}</style>
<div style='display:flex;gap:6px;padding:3px 0;'>
  {"".join(
    f'<div style="flex:1;height:2px;border-radius:1px;background:{"#00c65e" if lbl==_ql_active_label else "#1a1a1a"};"></div>'
    for lbl in ["🇬🇧 EN","🇫🇷 FR","🇸🇦 AR","🇹🇷 TR"]
  )}
</div>""", height=12, scrolling=False)

    st.markdown("<div style='height:2px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns([3, 1], gap="small")
    with c1:
        _aud_vals = list(AUDIENCE_LANGS.values())
        _aud_idx = _aud_vals.index(st.session_state.aud_lang) if st.session_state.aud_lang in _aud_vals else 0
        lc_sel = st.selectbox(
            "Language",
            list(AUDIENCE_LANGS.keys()),
            index=_aud_idx,
            label_visibility="collapsed",
            key="aud_lang_sel",
        )
        st.session_state.aud_lang = AUDIENCE_LANGS[lc_sel]
    with c2:
        rate = st.selectbox(
            "Refresh",
            [2, 3, 5, 8],
            index=1,
            format_func=lambda x: f"↺{x}s",
            label_visibility="collapsed",
            key="aud_rate_sel",
        )
        st.session_state.aud_rate = rate

    f1, f2, f3 = st.columns([1, 2, 1], gap="small")
    with f1:
        if st.button("A−", key="fdn", use_container_width=True):
            st.session_state.aud_fpx = max(16, st.session_state.aud_fpx - 4)
    with f2:
        fpx = st.session_state.aud_fpx
        st.markdown(f"""
<div style='text-align:center;font-size:12px;color:#444;
  font-family:monospace;padding:9px 0;'>
  font <b style='color:#666;'>{fpx}px</b>
</div>""", unsafe_allow_html=True)
    with f3:
        if st.button("A+", key="fup", use_container_width=True):
            st.session_state.aud_fpx = min(64, st.session_state.aud_fpx + 4)

    # Wake lock
    components.html("""<script>
(async()=>{
  if('wakeLock' in navigator){
    try{await navigator.wakeLock.request('screen');}catch(e){}
    document.addEventListener('visibilitychange',async()=>{
      if(document.visibilityState==='visible')
        try{await navigator.wakeLock.request('screen');}catch(e){}
    });
  }
})();
</script>""", height=0, scrolling=False)

    # ── live fragment ─────────────────────────────────────────────────────────
    @st.fragment(run_every=st.session_state.aud_rate)
    def live_display():
        tgt  = st.session_state.aud_lang
        fpx  = st.session_state.aud_fpx
        rows = db_all(room, 25)
        n    = db_count(room)

        # Direction for the TARGET language (what the audience reads)
        tgt_dir   = dir_attr(tgt)
        tgt_style = rtl_style(tgt)
        # Choose font based on target
        tgt_font  = (
            "'Noto Naskh Arabic','Cairo',sans-serif"
            if tgt_dir == "rtl"
            else "'Cairo',sans-serif"
        )

        components.html(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
body{{margin:0;padding:2px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:7px;padding:7px 12px;
  background:#0d0d0d;border:1px solid #1a1a1a;border-radius:8px;
  font-size:11px;font-family:monospace;'>
  <span style='width:7px;height:7px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.15);
    animation:dp 1.4s infinite;flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    🔴 Live · <b>{n}</b> segs · Room <b>{esc(room)}</b> · <b>{esc(tgt.upper())}</b> · ↺{st.session_state.aud_rate}s
  </span>
</div>""", height=38, scrolling=False)

        if not rows:
            components.html(PALETTE + """
<style>body{padding:30px 0;text-align:center;background:transparent;}</style>
<div style='font-size:42px;margin-bottom:9px'>⏳</div>
<div style='font-size:14px;color:#2a2a2a;'>Waiting for speaker…</div>
<div style='font-size:11px;color:#1a1a1a;margin-top:5px;'>
  The speaker will broadcast to this room</div>
""", height=150)
            return

        ltxt, llang, lts = rows[0]
        ltranslated = tr(ltxt, tgt, llang)

        # Source display (show original if different language & different text)
        src_dir = dir_attr(llang)
        src_style = rtl_style(llang)
        src_font = (
            "'Noto Naskh Arabic','Cairo',sans-serif"
            if src_dir == "rtl"
            else "'Cairo',sans-serif"
        )
        show_src = (
            _norm_for_google(llang) != _norm_for_google(tgt)
            and esc(ltxt) != esc(ltranslated)
        )
        src_div = (
            f'<div class="so" dir="{src_dir}" '
            f'style="{src_style}font-family:{src_font};">'
            f'{esc(llang).upper()}: {esc(ltxt)}</div>'
            if show_src else ""
        )

        # JS-safe escaped string for speak/copy (use JSON.stringify-safe repr)
        import json
        js_translated = json.dumps(ltranslated)  # gives "\"...\""

        components.html(PALETTE + f"""
<style>
body{{padding:5px 0 3px;background:transparent;}}
.stage{{
  background:#0a0a0a;border:1px solid #1a1a1a;border-radius:16px;
  padding:22px 18px;position:relative;overflow:hidden;
  display:flex;flex-direction:column;justify-content:center;min-height:110px;
}}
.stage::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#0a0a0a 35%,#007a3d 100%);}}
.so{{
  font-size:11px;color:#2a2a2a;font-style:italic;
  margin-bottom:9px;padding-bottom:9px;border-bottom:1px solid #181818;
  line-height:1.6;
}}
.st{{
  color:#f2ede3;font-weight:700;line-height:1.65;
  font-size:{fpx}px;animation:fi .4s ease;
  font-family:{tgt_font};
  {tgt_style}
}}
@keyframes fi{{from{{opacity:.1;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.sm{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#1e1e1e;margin-top:11px;}}
</style>
<div class="stage">
  {src_div}
  <div class="st" dir="{tgt_dir}">{esc(ltranslated)}</div>
  <div class="sm">🕐 {esc(lts)} · {esc((llang or "?").upper())} → {esc(tgt.upper())}</div>
</div>
""", height=max(170, fpx * 3 + 75), scrolling=False)

        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 5px;}}
.row{{display:flex;gap:8px;}}
.btn{{
  flex:1;background:#141414;border:1px solid #1e1e1e;border-radius:10px;
  padding:12px 8px;color:#444;font-size:12px;cursor:pointer;
  font-family:'Cairo',sans-serif;font-weight:700;text-align:center;
  -webkit-tap-highlight-color:transparent;transition:all .15s;
}}
.btn:active{{background:#1e1e1e;color:#f2ede3;transform:scale(.96);}}
.btn:hover{{background:#1e1e1e;color:#f2ede3;border-color:#2e2e2e;}}
#cm{{color:#00c65e;font-size:11px;opacity:0;transition:opacity .3s;align-self:center;}}
#fs{{display:none;position:fixed;inset:0;background:#000;z-index:99999;
  align-items:center;justify-content:center;cursor:pointer;
  flex-direction:column;text-align:{("right" if tgt_dir == "rtl" else "left")};padding:32px;}}
#fs-t{{
  color:#f2ede3;font-weight:700;line-height:1.45;
  font-size:clamp(28px,8vw,80px);max-width:95%;
  direction:{tgt_dir};
  font-family:{tgt_font};
}}
#fs-b{{position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126,#000 30%,#007a3d);}}
#fs-h{{position:absolute;bottom:16px;font-size:11px;color:#1a1a1a;font-family:monospace;}}
</style>
<div class="row">
  <button class="btn" onclick="speak()">🔊 Aloud</button>
  <button class="btn" onclick="copy()">📋 Copy</button>
  <button class="btn" onclick="openfs()">⛶ Full</button>
  <span id="cm">✓ Copied</span>
</div>
<div id="fs" onclick="closefs()">
  <div id="fs-t" dir="{tgt_dir}">{esc(ltranslated)}</div>
  <div id="fs-h">Tap to close</div>
  <div id="fs-b"></div>
</div>
<script>
const T={js_translated}, L="{esc(tgt)}";
function speak(){{
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(T);
  u.lang=L;
  speechSynthesis.speak(u);
}}
function copy(){{
  navigator.clipboard.writeText(T).then(()=>{{
    const m=document.getElementById('cm');
    m.style.opacity='1';
    setTimeout(()=>m.style.opacity='0',2000);
  }}).catch(()=>{{}});
  if(navigator.vibrate)navigator.vibrate(40);
}}
function openfs(){{document.getElementById('fs').style.display='flex';}}
function closefs(){{document.getElementById('fs').style.display='none';}}
</script>
""", height=58, scrolling=False)

        older = rows[1:]
        if older:
            st.markdown("""
<div style='margin:3px 0 5px;font-size:10px;color:#333;
  font-family:monospace;letter-spacing:.1em;text-align:center;'>─── PREVIOUS ───</div>
""", unsafe_allow_html=True)

            h_html = ""
            for st_txt, sl, sts in older:
                s_tr    = tr(st_txt, tgt, sl)
                d2      = dir_attr(tgt)     # display direction = target
                rs2     = rtl_style(tgt)
                f2      = (
                    "'Noto Naskh Arabic','Cairo',sans-serif"
                    if d2 == "rtl" else "'Cairo',sans-serif"
                )
                src_d2  = dir_attr(sl)
                src_rs2 = rtl_style(sl)
                src_f2  = (
                    "'Noto Naskh Arabic','Cairo',sans-serif"
                    if src_d2 == "rtl" else "'Cairo',sans-serif"
                )
                show_src2 = (
                    _norm_for_google(sl) != _norm_for_google(tgt)
                    and esc(st_txt) != esc(s_tr)
                )
                so_d = (
                    f'<div class="ao" dir="{src_d2}" '
                    f'style="{src_rs2}font-family:{src_f2};">'
                    f'{esc(sl).upper()}: {esc(st_txt)}</div>'
                    if show_src2 else ""
                )
                h_html += f"""
<div class="ac">
  {so_d}
  <div class="at" dir="{d2}" style="{rs2}font-family:{f2};">{esc(s_tr)}</div>
  <div class="ats">🕐 {esc(sts)}</div>
</div>"""

            components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:2px 0 20px;}}
.ac{{background:#111;border:1px solid #202020;border-radius:10px;
  padding:11px 13px;margin:4px 0;opacity:.75;transition:opacity .2s;}}
.ac:hover{{opacity:1;border-color:#2e2e2e;}}
.ao{{font-size:11px;color:#555;font-style:italic;margin-bottom:3px;line-height:1.5;}}
.at{{font-size:15px;font-weight:600;color:#f2ede3;line-height:1.65;}}
.ats{{font-size:10px;color:#333;font-family:'JetBrains Mono',monospace;margin-top:3px;}}
</style>
{h_html}
""", height=min(50 + len(older) * 84, 1800), scrolling=True)

    live_display()
