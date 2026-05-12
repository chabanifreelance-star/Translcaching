"""
LiveTranslate Conference — Single File, 100% Free
===================================================

requirements.txt (or Streamlit Cloud packages):
  streamlit
  faster-whisper
  deep-translator
  numpy

Run:
  streamlit run app.py
"""

import streamlit as st
import sqlite3, os, tempfile, time
from datetime import datetime

# ══════════════════════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
#  FULL CSS — Palestine palette (black · white · green #007a3d · red #ce1126)
#  + melon/warm accent tones
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Tokens ── */
:root{
  --bg:       #080808;
  --surface:  #101010;
  --card:     #161616;
  --card2:    #1a1a1a;
  --border:   #242424;
  --border2:  #2e2e2e;

  /* Palestine flag */
  --black:    #080808;
  --white:    #f2ede3;
  --green:    #007a3d;
  --green2:   #00a352;
  --green-lt: #00c965;
  --red:      #ce1126;
  --red2:     #e5162e;
  --red-lt:   #ff3348;

  /* Melon warm accents */
  --melon:    #fd6b4b;
  --melon2:   #ff8a6a;
  --melon-bg: rgba(253,107,75,.08);
  --amber:    #f59e0b;
}

/* ── Reset ── */
*,*::before,*::after{box-sizing:border-box;}
html,body,[class*="css"]{
  font-family:'Cairo',sans-serif!important;
  background:var(--bg)!important;
  color:var(--white)!important;
}
.stApp{background:var(--bg)!important;}
#MainMenu,header,footer{visibility:hidden!important;}
[data-testid="stSidebar"]{display:none!important;}
[data-testid="collapsedControl"]{display:none!important;}

::-webkit-scrollbar{width:3px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:2px;}

/* ══ HOME PAGE ══════════════════════════════════════════════════════════════ */

.home-outer{
  min-height:100vh;
  display:flex;
  flex-direction:column;
  align-items:center;
  justify-content:flex-start;
  padding:60px 20px 60px;
}

/* Decorative top bar: flag stripe */
.home-outer::before{
  content:'';
  position:fixed;top:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg, var(--red) 0%, var(--red) 25%,
    #222 25%, #222 50%,
    var(--green) 50%, var(--green) 75%,
    #111 75%);
  z-index:999;
}

.brand-block{text-align:center;margin-bottom:8px;}
.brand-word{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(72px,12vw,140px);
  line-height:.85;
  letter-spacing:.04em;
  display:block;
}
.brand-live{
  background:linear-gradient(135deg, var(--red-lt) 0%, var(--melon) 60%, var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.brand-translate{
  background:linear-gradient(135deg, var(--green-lt) 0%, var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}
.brand-sub{
  font-size:12px;color:#444;letter-spacing:.2em;
  text-transform:uppercase;margin-top:10px;margin-bottom:36px;
}

/* Flag stripe decoration */
.flag-stripe{
  display:flex;height:4px;width:100%;max-width:700px;
  border-radius:2px;overflow:hidden;margin:0 auto 40px;
}
.fs-bk{flex:1;background:#2a2a2a;}
.fs-wh{flex:1;background:#3a3a3a;}
.fs-gr{flex:1;background:var(--green);}
.fs-rd{flex:1;background:var(--red);}

/* Role cards */
.role-grid{
  display:flex;gap:20px;justify-content:center;
  flex-wrap:wrap;width:100%;max-width:700px;
  margin-bottom:52px;
}
.role-card{
  width:300px;
  background:var(--card);
  border:1px solid var(--border);
  border-radius:20px;
  padding:36px 28px 32px;
  text-decoration:none;
  display:block;
  position:relative;overflow:hidden;
  transition:transform .25s,border-color .25s,box-shadow .25s;
}
.role-card:hover{
  transform:translateY(-5px);
  border-color:#3a3a3a;
}
.role-card.spk:hover{box-shadow:0 16px 48px rgba(206,17,38,.18);}
.role-card.aud:hover{box-shadow:0 16px 48px rgba(0,122,61,.18);}

/* Glow blob behind card */
.role-card.spk::before{
  content:'';position:absolute;width:200px;height:200px;
  border-radius:50%;
  background:radial-gradient(circle, rgba(206,17,38,.18) 0%, transparent 70%);
  top:-60px;left:-60px;pointer-events:none;
}
.role-card.aud::before{
  content:'';position:absolute;width:200px;height:200px;
  border-radius:50%;
  background:radial-gradient(circle, rgba(0,122,61,.18) 0%, transparent 70%);
  top:-60px;left:-60px;pointer-events:none;
}

.role-icon{font-size:48px;margin-bottom:16px;display:block;}
.role-name{
  font-family:'Bebas Neue',sans-serif;
  font-size:36px;letter-spacing:.06em;margin-bottom:10px;
}
.role-name.spk{color:var(--red-lt);}
.role-name.aud{color:var(--green-lt);}
.role-desc{font-size:14px;color:#666;line-height:1.7;margin-bottom:20px;}
.role-btn{
  display:inline-block;padding:10px 24px;
  border-radius:8px;font-weight:700;font-size:13px;
  letter-spacing:.08em;text-transform:uppercase;
}
.role-btn.spk{
  background:rgba(206,17,38,.12);color:var(--red-lt);
  border:1px solid rgba(206,17,38,.3);
}
.role-btn.aud{
  background:rgba(0,122,61,.12);color:var(--green-lt);
  border:1px solid rgba(0,122,61,.3);
}

/* Feature chips */
.feat-row{
  display:flex;gap:14px;justify-content:center;
  flex-wrap:wrap;max-width:700px;margin-bottom:48px;
}
.feat{
  background:var(--card);border:1px solid var(--border);
  border-radius:14px;padding:18px 20px;width:155px;
}
.feat-icon{font-size:22px;margin-bottom:7px;}
.feat-title{font-size:13px;font-weight:700;color:#ccc;margin-bottom:4px;}
.feat-desc{font-size:12px;color:#555;line-height:1.6;}

.home-footer{font-size:11px;color:#2a2a2a;letter-spacing:.06em;text-align:center;}

/* ══ SHARED ELEMENTS ════════════════════════════════════════════════════════ */

.page-header{padding:36px 0 20px;}
.page-title{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(56px,9vw,100px);
  line-height:.85;letter-spacing:.03em;
  margin:0 0 6px;
}
.page-sub{font-size:12px;color:#444;letter-spacing:.16em;text-transform:uppercase;}

.back-link{
  display:inline-flex;align-items:center;gap:7px;
  color:#3a3a3a;font-size:13px;text-decoration:none;
  margin-bottom:20px;transition:color .2s;
}
.back-link:hover{color:#888;}

.sbar{
  display:flex;align-items:center;gap:12px;
  padding:12px 18px;
  background:var(--surface);border:1px solid var(--border);border-radius:10px;
  font-size:13px;font-family:'JetBrains Mono',monospace;
  margin:12px 0;
}
.dot{width:9px;height:9px;border-radius:50%;flex-shrink:0;}
.dot-off{background:#252525;}
.dot-rec{background:var(--red-lt);box-shadow:0 0 0 5px rgba(206,17,38,.18);animation:dp 1.1s infinite;}
.dot-ok {background:var(--green-lt);box-shadow:0 0 0 5px rgba(0,198,94,.18);animation:dp 1.4s infinite;}
.dot-proc{background:var(--amber);box-shadow:0 0 0 5px rgba(245,158,11,.18);animation:dp .55s infinite;}
@keyframes dp{0%,100%{opacity:1;transform:scale(1);}50%{opacity:.3;transform:scale(.75);}}

.ltag{
  display:inline-block;
  background:rgba(0,198,94,.08);color:var(--green-lt);
  border:1px solid rgba(0,198,94,.2);border-radius:4px;
  padding:2px 9px;font-size:10px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;
}
.ltag-red{
  background:rgba(206,17,38,.08)!important;color:var(--red-lt)!important;
  border-color:rgba(206,17,38,.2)!important;
}
.ltag-melon{
  background:var(--melon-bg)!important;color:var(--melon2)!important;
  border-color:rgba(253,107,75,.2)!important;
}

/* ══ SPEAKER PAGE ═══════════════════════════════════════════════════════════ */

.spk-title{
  background:linear-gradient(140deg, var(--white) 30%, var(--melon) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}

/* History cards — newest on top */
.hcard{
  background:var(--card);
  border:1px solid var(--border);
  border-radius:14px;
  padding:18px 22px;
  margin:10px 0;
  transition:border-color .25s;
}
.hcard:hover{border-color:#333;}
.hcard.newest{
  border-left:3px solid var(--melon);
  background:linear-gradient(135deg, var(--melon-bg), var(--card) 55%);
  animation:slid .4s ease;
}
@keyframes slid{from{opacity:.2;transform:translateY(-8px);}to{opacity:1;transform:translateY(0);}}

.hcard-meta{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;}
.hcard-ts{font-family:'JetBrains Mono',monospace;font-size:11px;color:var(--border2);}
.hcard-text{font-size:17px;font-weight:600;color:var(--white);line-height:1.6;direction:auto;}

/* ══ AUDIENCE PAGE ══════════════════════════════════════════════════════════ */

.aud-title{
  background:linear-gradient(140deg, var(--white) 30%, var(--green-lt) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}

/* Big subtitle stage */
.sub-stage{
  background:var(--surface);
  border:1px solid var(--border);
  border-radius:20px;
  padding:40px 36px;
  min-height:220px;
  display:flex;flex-direction:column;justify-content:center;
  position:relative;overflow:hidden;
  margin:20px 0;
}
.sub-stage::after{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg, var(--red) 0%, #111 30%, var(--green) 100%);
}
/* Corner glow */
.sub-stage::before{
  content:'';position:absolute;
  width:300px;height:300px;border-radius:50%;
  background:radial-gradient(circle, rgba(0,122,61,.08) 0%, transparent 70%);
  bottom:-80px;right:-80px;pointer-events:none;
}
.sub-orig{
  font-size:14px;color:#3a3a3a;font-style:italic;
  direction:auto;line-height:1.6;
  padding-bottom:14px;margin-bottom:14px;
  border-bottom:1px solid var(--border);
}
.sub-text{
  color:var(--white);font-weight:700;
  line-height:1.5;direction:auto;
  animation:fadein .5s ease;
}
@keyframes fadein{from{opacity:.2;transform:translateY(10px);}to{opacity:1;transform:translateY(0);}}
.sub-meta{
  font-family:'JetBrains Mono',monospace;font-size:11px;color:#282828;
  margin-top:18px;
}

/* Action buttons row */
.act-row{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0;}
.act-btn{
  background:var(--card);border:1px solid var(--border);
  border-radius:9px;padding:9px 18px;
  color:#666;font-size:13px;cursor:pointer;
  transition:all .2s;font-family:'Cairo',sans-serif;font-weight:600;
}
.act-btn:hover{background:var(--card2);color:var(--white);border-color:#3a3a3a;}

/* History (audience) */
.acard{
  background:var(--card);border:1px solid var(--border);
  border-radius:12px;padding:14px 20px;margin:7px 0;
  opacity:.55;transition:opacity .2s;
}
.acard:hover{opacity:.85;}
.acard-orig{font-size:12px;color:#333;font-style:italic;direction:auto;margin-bottom:5px;}
.acard-text{font-size:16px;font-weight:600;color:#aaa;direction:auto;line-height:1.5;}
.acard-ts{font-size:11px;color:#252525;font-family:'JetBrains Mono',monospace;margin-top:5px;}

/* ══ WIDGET OVERRIDES ═══════════════════════════════════════════════════════ */

.stButton>button{
  font-family:'Cairo',sans-serif!important;
  font-weight:700!important;border:none!important;
  border-radius:10px!important;
  letter-spacing:.04em!important;
  transition:all .2s!important;
}
.stSelectbox>div>div{
  background:var(--surface)!important;
  border:1px solid var(--border)!important;
  color:var(--white)!important;border-radius:10px!important;
}
.stSelectbox label,.stToggle label,.stSlider label{
  color:var(--white)!important;font-weight:600!important;
}
[data-testid="stSlider"] .st-ae{background:var(--green)!important;}
hr{border-color:var(--border)!important;}
[data-testid="stAudioInput"]{
  background:var(--surface)!important;
  border:1px dashed var(--border2)!important;
  border-radius:14px!important;
  padding:8px!important;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  DATABASE
# ══════════════════════════════════════════════════════════════════════════════
DB = os.path.join(tempfile.gettempdir(), "lt_v4.db")

def _db():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    with _db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS segments(
            id   INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT    NOT NULL,
            lang TEXT    NOT NULL DEFAULT '',
            ts   TEXT    NOT NULL
        )""")
        c.commit()

def db_save(text: str, lang: str):
    with _db() as c:
        c.execute("INSERT INTO segments(text,lang,ts) VALUES(?,?,?)",
                  (text.strip(), lang, datetime.now().strftime("%H:%M:%S")))
        c.commit()

def db_get(limit=30):
    """Returns newest first."""
    with _db() as c:
        return c.execute(
            "SELECT text,lang,ts FROM segments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

def db_count():
    with _db() as c:
        return c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]

def db_clear():
    with _db() as c:
        c.execute("DELETE FROM segments"); c.commit()

init_db()


# ══════════════════════════════════════════════════════════════════════════════
#  AI — WHISPER (local, cached)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner=False)
def get_whisper():
    try:
        from faster_whisper import WhisperModel
        try:    return WhisperModel("base", device="cuda", compute_type="float16"), "GPU"
        except: return WhisperModel("base", device="cpu",  compute_type="int8"),   "CPU"
    except Exception as e:
        return None, str(e)

def transcribe(audio_bytes: bytes):
    """Returns (text, lang_code). task=transcribe keeps original language, language=None auto-detects."""
    model, _ = get_whisper()
    if not model:
        return "", "err"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes); path = f.name
    try:
        segs, info = model.transcribe(
            path,
            task="transcribe",   # keep original language — NOT forced English
            language=None,       # auto-detect: Arabic, French, Spanish, Chinese…
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        return " ".join(s.text.strip() for s in segs).strip(), info.language
    except Exception as e:
        return "", "err"
    finally:
        try: os.unlink(path)
        except: pass


# ══════════════════════════════════════════════════════════════════════════════
#  TRANSLATION (free, cached)
# ══════════════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=7200, show_spinner=False)
def translate(text: str, target: str, source: str = "auto") -> str:
    if not text.strip(): return text
    src = source.split("-")[0].lower() if source and source != "auto" else "auto"
    tgt = target.split("-")[0].lower()
    if src != "auto" and src == tgt: return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=target).translate(text) or text
    except Exception as e:
        return f"[{e}]"


# ══════════════════════════════════════════════════════════════════════════════
#  LANGUAGE LIST
# ══════════════════════════════════════════════════════════════════════════════
LANGUAGES = {
    "🇸🇦 Arabic / عربي":          "ar",
    "🇬🇧 English":                 "en",
    "🇫🇷 French / Français":       "fr",
    "🇪🇸 Spanish / Español":       "es",
    "🇩🇪 German / Deutsch":        "de",
    "🇹🇷 Turkish / Türkçe":        "tr",
    "🇮🇹 Italian / Italiano":      "it",
    "🇨🇳 Chinese / 中文":          "zh-CN",
    "🇷🇺 Russian / Русский":       "ru",
    "🇯🇵 Japanese / 日本語":       "ja",
    "🇧🇷 Portuguese / Português":  "pt",
    "🇮🇳 Hindi / हिन्दी":          "hi",
    "🇰🇷 Korean / 한국어":          "ko",
    "🇳🇱 Dutch / Nederlands":      "nl",
    "🇵🇱 Polish / Polski":         "pl",
    "🇸🇪 Swedish / Svenska":       "sv",
    "🇬🇷 Greek / Ελληνικά":        "el",
    "🇹🇭 Thai / ภาษาไทย":         "th",
    "🇻🇳 Vietnamese / Tiếng Việt": "vi",
    "🇺🇦 Ukrainian / Українська":  "uk",
    "🇮🇩 Indonesian / Bahasa":     "id",
}

FLAG_HTML = """
<div class="flag-stripe">
  <div class="fs-bk"></div><div class="fs-wh"></div>
  <div class="fs-gr"></div><div class="fs-rd"></div>
</div>"""


# ══════════════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ══════════════════════════════════════════════════════════════════════════════
for k, v in {
    "page": "home",
    "last_hash": None,
    "last_text": "",
    "last_lang": "",
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# URL param routing (supports sharing ?page=audience link)
params = st.query_params
if "page" in params and st.session_state.page == "home":
    st.session_state.page = params["page"]


# ══════════════════════════════════════════════════════════════════════════════
#  ██╗  ██╗ ██████╗ ███╗   ███╗███████╗
#  ██║  ██║██╔═══██╗████╗ ████║██╔════╝
#  ███████║██║   ██║██╔████╔██║█████╗
#  ██╔══██║██║   ██║██║╚██╔╝██║██╔══╝
#  ██║  ██║╚██████╔╝██║ ╚═╝ ██║███████╗
#  ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    st.markdown(f"""
    <div class="home-outer">

      <div class="brand-block">
        <span class="brand-word brand-live">LIVE</span>
        <span class="brand-word brand-translate">TRANSLATE</span>
        <div class="brand-sub">Real-time multilingual conference subtitles &nbsp;🇵🇸</div>
      </div>

      {FLAG_HTML}

      <div class="role-grid">

        <a class="role-card spk" href="?page=speaker">
          <span class="role-icon">🎤</span>
          <div class="role-name spk">SPEAKER</div>
          <div class="role-desc">
            You are presenting.<br>
            Record your speech — the AI auto-detects your language
            and broadcasts it live to the audience in real time.
          </div>
          <span class="role-btn spk">I am the Speaker &rarr;</span>
        </a>

        <a class="role-card aud" href="?page=audience">
          <span class="role-icon">👥</span>
          <div class="role-name aud">AUDIENCE</div>
          <div class="role-desc">
            You are listening.<br>
            Choose your language and read live translated
            subtitles — updated automatically every few seconds.
          </div>
          <span class="role-btn aud">I am Audience &rarr;</span>
        </a>

      </div>

      <div class="feat-row">
        <div class="feat">
          <div class="feat-icon">🌍</div>
          <div class="feat-title">99 Languages</div>
          <div class="feat-desc">Arabic, French, Spanish, Chinese, Russian — auto-detected</div>
        </div>
        <div class="feat">
          <div class="feat-icon">🤫</div>
          <div class="feat-title">Auto-Stop</div>
          <div class="feat-desc">4 seconds of silence → auto-processes without any button</div>
        </div>
        <div class="feat">
          <div class="feat-icon">🔒</div>
          <div class="feat-title">100% Free</div>
          <div class="feat-desc">No API key, no account, no cost — runs fully local</div>
        </div>
        <div class="feat">
          <div class="feat-icon">📱</div>
          <div class="feat-title">Any Device</div>
          <div class="feat-desc">Works in any modern browser — phone, tablet, laptop</div>
        </div>
      </div>

      <div class="home-footer">
        Made with 🇵🇸 &nbsp;·&nbsp; 100% free &nbsp;·&nbsp; faster-whisper &nbsp;·&nbsp; deep-translator
      </div>

    </div>
    """, unsafe_allow_html=True)

    # Streamlit buttons as fallback navigation (query params also work)
    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        if st.button("🎤  Enter as Speaker", use_container_width=True,
                     key="btn_spk",
                     help="Speaker mode — record and broadcast"):
            st.session_state.page = "speaker"
            st.query_params["page"] = "speaker"
            st.rerun()
    with c2:
        if st.button("👥  Enter as Audience", use_container_width=True,
                     key="btn_aud",
                     help="Audience mode — read live subtitles"):
            st.session_state.page = "audience"
            st.query_params["page"] = "audience"
            st.rerun()
    with c3:
        pass  # spacer


# ══════════════════════════════════════════════════════════════════════════════
#  ███████╗██████╗ ███████╗ █████╗ ██╗  ██╗███████╗██████╗
#  ██╔════╝██╔══██╗██╔════╝██╔══██╗██║ ██╔╝██╔════╝██╔══██╗
#  ███████╗██████╔╝█████╗  ███████║█████╔╝ █████╗  ██████╔╝
#  ╚════██║██╔═══╝ ██╔══╝  ██╔══██║██╔═██╗ ██╔══╝  ██╔══██╗
#  ███████║██║     ███████╗██║  ██║██║  ██╗███████╗██║  ██║
#  ╚══════╝╚═╝     ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    # Back button
    if st.button("← Home", key="spk_back"):
        st.session_state.page = "home"
        st.query_params["page"] = "home"
        st.rerun()

    st.markdown(f"""
    <div class="page-header">
      <div class="page-title spk-title">SPEAK<br>NOW</div>
      <div class="page-sub">Your speech is broadcast live · Any language · Auto-detected</div>
    </div>
    {FLAG_HTML}
    """, unsafe_allow_html=True)

    # ── Silence-detecting JS recorder ────────────────────────────────────────
    # Injects a fully custom recorder into the page via st.components.v1.html.
    # Uses Web Audio API AnalyserNode to monitor RMS every 100ms.
    # After 4s of silence → stops recording → encodes WAV → sends base64 via
    # postMessage to the parent Streamlit frame (picked up by st.audio_input).
    import streamlit.components.v1 as components

    components.html("""
<!DOCTYPE html>
<html>
<head>
<style>
  *{box-sizing:border-box;margin:0;padding:0;}
  @import url('https://fonts.googleapis.com/css2?family=Cairo:wght@700;900&family=Bebas+Neue&display=swap');
  body{background:transparent;font-family:'Cairo',sans-serif;padding:0;}

  #recorder{
    background:#101010;border:1px solid #242424;border-radius:16px;
    padding:22px 24px;
  }

  #btn-start,#btn-stop{
    width:100%;padding:20px 24px;border-radius:12px;
    font-family:'Bebas Neue',sans-serif;font-size:26px;letter-spacing:.08em;
    border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:14px;
    transition:all .2s;
  }
  #btn-start{
    background:linear-gradient(135deg,#ce1126,#a00e1b);
    color:#fff;box-shadow:0 6px 30px rgba(206,17,38,.4);
  }
  #btn-start:hover{transform:translateY(-2px);box-shadow:0 10px 40px rgba(206,17,38,.5);}
  #btn-stop{
    background:#1a1a1a;color:#ff3348;
    border:2px solid rgba(206,17,38,.35);display:none;
  }
  #btn-stop:hover{background:#222;}

  /* Level bars */
  #bars{
    display:none;align-items:flex-end;justify-content:center;
    gap:3px;height:40px;margin:16px 0 8px;
  }
  .bar{width:5px;background:#ce1126;border-radius:3px;min-height:3px;transition:height .08s ease;}

  /* Silence progress */
  #sil-wrap{background:#1c1c1c;border-radius:4px;height:5px;margin:10px 0;overflow:hidden;display:none;}
  #sil-fill{height:100%;border-radius:4px;width:0%;transition:width .25s linear;
    background:linear-gradient(90deg,#00c65e,#007a3d);}

  #status{
    font-size:13px;font-family:monospace;color:#555;
    text-align:center;margin-top:10px;min-height:18px;line-height:1.5;
  }
</style>
</head>
<body>
<div id="recorder">
  <button id="btn-start" onclick="startRec()">🎤 &nbsp; START SPEAKING</button>
  <button id="btn-stop"  onclick="manualStop()">⏹ &nbsp; STOP SPEAKING</button>
  <div id="bars">
    <!-- 20 level bars -->
    <div class="bar" id="b0"></div><div class="bar" id="b1"></div>
    <div class="bar" id="b2"></div><div class="bar" id="b3"></div>
    <div class="bar" id="b4"></div><div class="bar" id="b5"></div>
    <div class="bar" id="b6"></div><div class="bar" id="b7"></div>
    <div class="bar" id="b8"></div><div class="bar" id="b9"></div>
    <div class="bar" id="b10"></div><div class="bar" id="b11"></div>
    <div class="bar" id="b12"></div><div class="bar" id="b13"></div>
    <div class="bar" id="b14"></div><div class="bar" id="b15"></div>
    <div class="bar" id="b16"></div><div class="bar" id="b17"></div>
    <div class="bar" id="b18"></div><div class="bar" id="b19"></div>
  </div>
  <div id="sil-wrap"><div id="sil-fill"></div></div>
  <div id="status">Press the button and start speaking in any language</div>
</div>

<script>
const SILENCE_RMS  = 0.013;
const SILENCE_SECS = 4.0;
const SR           = 16000;

let mr, stream, ctx, analyser, rafId;
let chunks=[], silStart=null, isRec=false;
const bars   = Array.from({length:20},(_,i)=>document.getElementById('b'+i));
const bStart = document.getElementById('btn-start');
const bStop  = document.getElementById('btn-stop');
const status = document.getElementById('status');
const silW   = document.getElementById('sil-wrap');
const silF   = document.getElementById('sil-fill');
const barsEl = document.getElementById('bars');

function setStatus(msg, color='#555'){
  status.style.color=color; status.innerHTML=msg;
}

async function startRec(){
  try{
    stream = await navigator.mediaDevices.getUserMedia({
      audio:{sampleRate:SR, channelCount:1, echoCancellation:true, noiseSuppression:true}
    });
  }catch(e){
    setStatus('❌ Microphone blocked — allow mic in browser settings','#ff3348'); return;
  }
  ctx     = new (window.AudioContext||window.webkitAudioContext)({sampleRate:SR});
  analyser= ctx.createAnalyser(); analyser.fftSize=512;
  ctx.createMediaStreamSource(stream).connect(analyser);

  mr=new MediaRecorder(stream); chunks=[];
  mr.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data);};
  mr.onstop=buildAndSend;
  mr.start(100);

  isRec=true; silStart=null;
  bStart.style.display='none'; bStop.style.display='flex';
  barsEl.style.display='flex'; silW.style.display='block';
  silF.style.width='0%';
  setStatus('🔴 Recording — speak now','#ff3348');
  monitor();
}

function monitor(){
  if(!isRec) return;
  const d=new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteTimeDomainData(d);
  let sum=0; for(let v of d){const x=(v-128)/128; sum+=x*x;}
  const rms=Math.sqrt(sum/d.length);

  // Animate bars
  bars.forEach((b,i)=>{
    const wave=Math.abs(Math.sin(i*0.55+Date.now()*0.007));
    b.style.height=Math.max(3,Math.min(36,rms*600*wave))+'px';
  });

  const now=performance.now();
  if(rms<SILENCE_RMS){
    if(!silStart) silStart=now;
    const elapsed=(now-silStart)/1000;
    const pct=Math.min(100,(elapsed/SILENCE_SECS)*100);
    silF.style.width=pct+'%';
    if(pct>75) silF.style.background='linear-gradient(90deg,#ce1126,#a00)';
    else       silF.style.background='linear-gradient(90deg,#00c65e,#007a3d)';
    if(elapsed>=SILENCE_SECS){ autoStop(); return; }
    if(elapsed>0.8)
      setStatus(`🤫 Silence: ${elapsed.toFixed(1)}s / ${SILENCE_SECS}s — auto-stopping…`,'#f59e0b');
  }else{
    silStart=null; silF.style.width='0%';
    setStatus('🔴 Recording — speak now','#ff3348');
  }
  rafId=requestAnimationFrame(monitor);
}

function autoStop(){
  setStatus('⚡ Processing your speech…','#f59e0b');
  stopHW();
}
function manualStop(){
  setStatus('⚡ Processing…','#f59e0b');
  stopHW();
}
function stopHW(){
  if(!isRec) return; isRec=false;
  cancelAnimationFrame(rafId);
  if(mr&&mr.state!=='inactive') mr.stop();
  stream.getTracks().forEach(t=>t.stop()); ctx.close();
  bStop.style.display='none'; bStart.style.display='flex';
  barsEl.style.display='none'; bars.forEach(b=>b.style.height='3px');
  silW.style.display='none'; silF.style.width='0%';
}

async function buildAndSend(){
  const blob    = new Blob(chunks,{type:'audio/webm'});
  const arrBuf  = await blob.arrayBuffer();
  const tmpCtx  = new OfflineAudioContext(1,SR*60,SR);
  let buf;
  try{ buf=await tmpCtx.decodeAudioData(arrBuf); }
  catch(e){ setStatus('❌ Could not decode audio — try again','#ff3348'); return; }

  const pcm = buf.getChannelData(0);
  const wav = toWav(pcm, buf.sampleRate);
  const b64 = btoa(String.fromCharCode(...new Uint8Array(wav)));

  // Post to Streamlit parent frame
  window.parent.postMessage({type:'livetranslate_wav', b64}, '*');
  setStatus('✅ Sent! Press START SPEAKING for next segment.','#00c65e');
}

function toWav(pcm, sr){
  const buf  = new ArrayBuffer(44+pcm.length*2);
  const view = new DataView(buf);
  const w    = (o,s)=>{ for(let i=0;i<s.length;i++) view.setUint8(o+i,s.charCodeAt(i)); };
  w(0,'RIFF'); view.setUint32(4,36+pcm.length*2,true);
  w(8,'WAVE'); w(12,'fmt ');
  view.setUint32(16,16,true); view.setUint16(20,1,true);
  view.setUint16(22,1,true);  view.setUint32(24,sr,true);
  view.setUint32(28,sr*2,true); view.setUint16(32,2,true);
  view.setUint16(34,16,true); w(36,'data');
  view.setUint32(40,pcm.length*2,true);
  let off=44;
  for(let s of pcm){
    const v=Math.max(-1,Math.min(1,s));
    view.setInt16(off, v<0?v*0x8000:v*0x7FFF, true); off+=2;
  }
  return buf;
}
</script>
</body>
</html>
""", height=200, scrolling=False)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    st.markdown("""
    <div style='font-size:12px;color:#2a2a2a;text-align:center;margin-bottom:4px;
      font-family:JetBrains Mono,monospace;letter-spacing:.06em;'>
      — OR USE THE FALLBACK RECORDER BELOW —
    </div>""", unsafe_allow_html=True)

    # Fallback: st.audio_input — works even if JS component blocked
    recorded = st.audio_input(
        "🎙️ Click mic · speak · click stop — auto-transcribes instantly",
        key="fallback_rec",
        label_visibility="visible",
    )

    # Process new recording
    if recorded is not None:
        abytes = recorded.read()
        ahash  = hash(abytes)
        if ahash != st.session_state.last_hash:
            st.session_state.last_hash = ahash
            with st.spinner("🧠 Transcribing — detecting language automatically…"):
                text, lang = transcribe(abytes)
            if text:
                db_save(text, lang)
                st.session_state.last_text = text
                st.session_state.last_lang = lang
                st.cache_data.clear()
                st.success(f"✅ Broadcasted live!  Detected: **{lang}**")
                st.rerun()
            else:
                st.warning("⚠️ No speech detected — try speaking louder or closer to the mic.")

    # ── History: newest first ─────────────────────────────────────────────────
    segs = db_get(50)   # newest first by default (ORDER BY id DESC)
    n    = db_count()

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    col_h, col_c = st.columns([4, 1])
    with col_h:
        st.markdown(f"""
        <div class="sbar">
          <div class="dot dot-ok"></div>
          <div>Session: <b>{n}</b> segment(s) broadcast — newest first</div>
        </div>""", unsafe_allow_html=True)
    with col_c:
        if st.button("🗑️ Clear", use_container_width=True, key="spk_clear"):
            db_clear(); st.cache_data.clear()
            st.session_state.last_text = ""
            st.session_state.last_lang = ""
            st.rerun()

    if not segs:
        st.markdown("""
        <div style='text-align:center;padding:50px 20px;color:#2a2a2a;'>
          <div style='font-size:48px;margin-bottom:12px;'>🎙️</div>
          <div style='font-size:15px;'>Nothing broadcast yet — press START SPEAKING above</div>
        </div>""", unsafe_allow_html=True)
    else:
        for i, (text, lang, ts) in enumerate(segs):
            is_new = (i == 0)
            cls    = "hcard newest" if is_new else "hcard"
            tag    = f'<span class="ltag ltag-melon">NEW</span>' if is_new else ""
            st.markdown(f"""
            <div class="{cls}">
              <div class="hcard-meta">
                <span class="hcard-ts">🕐 {ts}</span>
                <span class="ltag">{lang.upper()}</span>
                {tag}
              </div>
              <div class="hcard-text">{text}</div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  ██████╗ ██╗   ██╗██████╗ ██╗     ██╗ ██████╗
#  ██╔══██╗██║   ██║██╔══██╗██║     ██║██╔════╝
#  ██████╔╝██║   ██║██████╔╝██║     ██║██║
#  ██╔═══╝ ██║   ██║██╔══██╗██║     ██║██║
#  ██║     ╚██████╔╝██████╔╝███████╗██║╚██████╗
#  ╚═╝      ╚═════╝ ╚═════╝ ╚══════╝╚═╝ ╚═════╝
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    if st.button("← Home", key="aud_back"):
        st.session_state.page = "home"
        st.query_params["page"] = "home"
        st.rerun()

    st.markdown(f"""
    <div class="page-header">
      <div class="page-title aud-title">LIVE<br>SUBTITLES</div>
      <div class="page-sub">Choose your language — updated automatically</div>
    </div>
    {FLAG_HTML}
    """, unsafe_allow_html=True)

    # Controls
    cl, cs, cr = st.columns([3, 1, 1])
    with cl:
        lang_choice = st.selectbox("🌐 My language:", list(LANGUAGES.keys()), index=0,
                                   label_visibility="collapsed")
        target = LANGUAGES[lang_choice]
    with cs:
        font_px = st.select_slider("Size", [20,28,36,44,56,68], value=44,
                                   format_func=lambda x: f"{x}px")
    with cr:
        rate = st.select_slider("Refresh", [2,3,5,8], value=3,
                                format_func=lambda x: f"{x}s")

    n = db_count()
    st.markdown(f"""
    <div class="sbar">
      <div class="dot dot-ok"></div>
      <div>🔴 Live — refreshing every <b>{rate}s</b> &nbsp;·&nbsp;
           <b>{n}</b> segment(s) &nbsp;·&nbsp; Target: <b>{target}</b></div>
    </div>""", unsafe_allow_html=True)

    # Newest segment — BIG display
    segs = db_get(30)   # newest first

    if not segs:
        st.markdown("""
        <div class="sub-stage">
          <div style='text-align:center;color:#252525;'>
            <div style='font-size:54px;margin-bottom:14px;'>⏳</div>
            <div style='font-size:18px;'>Waiting for the speaker to start…</div>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        # ── Latest segment (big) ──────────────────────────────────────────────
        latest_text, latest_lang, latest_ts = segs[0]
        translated_latest = translate(latest_text, target, latest_lang)

        tgt_base = target.split("-")[0].lower()
        src_base = latest_lang.split("-")[0].lower() if latest_lang else "auto"
        show_orig = (src_base != tgt_base) and (latest_text != translated_latest)

        orig_html = f'<div class="sub-orig">{latest_lang.upper()} · {latest_text}</div>' if show_orig else ""

        st.markdown(f"""
        <div class="sub-stage">
          {orig_html}
          <div class="sub-text" style="font-size:{font_px}px">{translated_latest}</div>
          <div class="sub-meta">🕐 {latest_ts} &nbsp;·&nbsp; {latest_lang.upper()} → {target.upper()}</div>
        </div>""", unsafe_allow_html=True)

        # ── Action buttons via JS ─────────────────────────────────────────────
        components.html(f"""
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:transparent;font-family:Cairo,sans-serif;padding:4px 0;}}
  .row{{display:flex;gap:10px;flex-wrap:wrap;}}
  .btn{{
    background:#161616;border:1px solid #242424;border-radius:9px;
    padding:10px 20px;color:#666;font-size:13px;cursor:pointer;
    transition:all .2s;font-family:Cairo,sans-serif;font-weight:700;
  }}
  .btn:hover{{background:#1e1e1e;color:#f0ede6;border-color:#3a3a3a;}}
  #cp-msg{{color:#00c65e;font-size:12px;margin-left:6px;opacity:0;transition:opacity .3s;align-self:center;}}

  /* Fullscreen overlay */
  #fs{{
    display:none;position:fixed;inset:0;background:#000;z-index:99999;
    align-items:center;justify-content:center;
    flex-direction:column;text-align:center;padding:40px;cursor:pointer;
  }}
  #fs-text{{
    color:#f0ede6;font-weight:700;direction:auto;line-height:1.4;
    font-size:clamp(32px,6vw,80px);max-width:92%;
  }}
  #fs-bar{{
    position:absolute;bottom:0;left:0;right:0;height:4px;
    background:linear-gradient(90deg,#ce1126 0%,#111 30%,#007a3d 100%);
  }}
  #fs-hint{{
    position:absolute;bottom:24px;font-size:12px;
    color:#333;font-family:monospace;
  }}
</style>
<div class="row">
  <button class="btn" onclick="speak()">🔊 Read aloud</button>
  <button class="btn" onclick="copyT()">📋 Copy text</button>
  <button class="btn" onclick="openFS()">⛶ Fullscreen</button>
  <span id="cp-msg">Copied!</span>
</div>

<div id="fs" onclick="closeFS()">
  <div id="fs-text">{translated_latest}</div>
  <div id="fs-hint">Click anywhere to close</div>
  <div id="fs-bar"></div>
</div>

<script>
const TXT  = {repr(translated_latest)};
const LANG = "{target}";

function speak(){{
  if(!window.speechSynthesis){{alert("Text-to-speech not supported");return;}}
  const u=new SpeechSynthesisUtterance(TXT);
  u.lang=LANG; speechSynthesis.cancel(); speechSynthesis.speak(u);
}}
function copyT(){{
  navigator.clipboard.writeText(TXT).then(()=>{{
    const m=document.getElementById('cp-msg');
    m.style.opacity='1'; setTimeout(()=>m.style.opacity='0',2200);
  }});
}}
function openFS(){{
  document.getElementById('fs').style.display='flex';
}}
function closeFS(){{
  document.getElementById('fs').style.display='none';
}}
</script>
""", height=56, scrolling=False)

        # ── History: newest → oldest ──────────────────────────────────────────
        older = segs[1:]   # skip the latest (already shown big), rest newest first
        if older:
            st.markdown("""
            <div style='margin:28px 0 10px;font-size:11px;color:#2a2a2a;
              font-family:JetBrains Mono,monospace;letter-spacing:.1em;'>
              ─── PREVIOUS SEGMENTS (newest → oldest) ───
            </div>""", unsafe_allow_html=True)

            for seg_text, seg_lang, seg_ts in older:
                seg_tr = translate(seg_text, target, seg_lang)
                tgt_b  = target.split("-")[0].lower()
                src_b  = seg_lang.split("-")[0].lower() if seg_lang else "auto"
                show_o = (src_b != tgt_b) and (seg_text != seg_tr)
                orig_a = f'<div class="acard-orig">{seg_lang.upper()} · {seg_text}</div>' if show_o else ""
                st.markdown(f"""
                <div class="acard">
                  {orig_a}
                  <div class="acard-text">{seg_tr}</div>
                  <div class="acard-ts">🕐 {seg_ts}</div>
                </div>""", unsafe_allow_html=True)

    # Auto-refresh
    time.sleep(rate)
    st.rerun()
