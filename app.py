"""
LiveTranslate Conference
========================
Requirements (Streamlit Cloud / requirements.txt):
  streamlit
  faster-whisper
  deep-translator
  numpy

Run locally:
  pip install streamlit faster-whisper deep-translator numpy
  streamlit run app.py
"""

import streamlit as st
import streamlit.components.v1 as components
import sqlite3, os, tempfile, time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="LiveTranslate", page_icon="🌐",
                   layout="wide", initial_sidebar_state="collapsed")

# Hide ALL Streamlit chrome
st.markdown("""
<style>
#MainMenu,header,footer,[data-testid="stSidebar"],[data-testid="collapsedControl"]
{display:none!important;visibility:hidden!important;}
.stApp{background:#080808!important;}
.block-container{padding:0!important;max-width:100%!important;}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# SHARED CSS injected into every components.html call
# ─────────────────────────────────────────────────────────────────────────────
PALETTE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');
:root{
  --bg:#080808; --s:#101010; --card:#161616; --card2:#1c1c1c;
  --b:#222; --b2:#2e2e2e;
  --white:#f2ede3; --muted:#555; --dim:#2a2a2a;
  --green:#007a3d; --gl:#00c65e; --g2:#00a352;
  --red:#ce1126;   --rl:#ff3348; --r2:#e5162e;
  --melon:#fd6b4b; --ml:#ff8a6a; --mbg:rgba(253,107,75,.08);
  --amber:#f59e0b;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{background:var(--bg);color:var(--white);
  font-family:'Cairo',sans-serif;-webkit-font-smoothing:antialiased;}
a{text-decoration:none;color:inherit;}
::-webkit-scrollbar{width:3px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:2px;}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# DATABASE
# ─────────────────────────────────────────────────────────────────────────────
DB = os.path.join(tempfile.gettempdir(), "lt_v5.db")

def _cx(): return sqlite3.connect(DB, check_same_thread=False)
def init_db():
    with _cx() as c:
        c.execute("CREATE TABLE IF NOT EXISTS seg(id INTEGER PRIMARY KEY AUTOINCREMENT,"
                  "txt TEXT NOT NULL,lang TEXT DEFAULT '',ts TEXT NOT NULL)")
        c.commit()
def db_save(txt, lang):
    with _cx() as c:
        c.execute("INSERT INTO seg(txt,lang,ts) VALUES(?,?,?)",
                  (txt.strip(), lang, datetime.now().strftime("%H:%M:%S")))
        c.commit()
def db_all(limit=40):          # newest first
    with _cx() as c:
        return c.execute("SELECT txt,lang,ts FROM seg ORDER BY id DESC LIMIT ?",
                         (limit,)).fetchall()
def db_count():
    with _cx() as c:
        return c.execute("SELECT COUNT(*) FROM seg").fetchone()[0]
def db_clear():
    with _cx() as c:
        c.execute("DELETE FROM seg"); c.commit()
init_db()

# ─────────────────────────────────────────────────────────────────────────────
# WHISPER  — now accepts an explicit language code
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_whisper():
    try:
        from faster_whisper import WhisperModel
        try:    return WhisperModel("base", device="cuda", compute_type="float16")
        except: return WhisperModel("base", device="cpu",  compute_type="int8")
    except: return None

def transcribe(b: bytes, lang_code: str = None):
    """Transcribe audio bytes.  lang_code: ISO-639-1 e.g. 'en','ar','fr'"""
    m = get_whisper()
    if not m: return "", lang_code or ""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(b); p = f.name
    try:
        segs, info = m.transcribe(
            p, task="transcribe",
            language=lang_code,          # None → auto-detect (unused now)
            beam_size=5, vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300}
        )
        detected = lang_code or info.language
        return " ".join(s.text.strip() for s in segs).strip(), detected
    except: return "", lang_code or ""
    finally:
        try: os.unlink(p)
        except: pass

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def tr(text, target, source="auto"):
    if not text.strip(): return text
    src = source.split("-")[0].lower() if source and source != "auto" else "auto"
    tgt = target.split("-")[0].lower()
    if src != "auto" and src == tgt: return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=target).translate(text) or text
    except Exception as e: return f"[{e}]"

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE LISTS
# ─────────────────────────────────────────────────────────────────────────────

# Speaker can choose from these 5 languages
SPEAKER_LANGS = {
    "🇬🇧 English":        "en",
    "🇸🇦 Arabic / عربي":  "ar",
    "🇫🇷 French":         "fr",
    "🇹🇷 Turkish":        "tr",
    "🇪🇸 Spanish":        "es",
}

# Audience picks any of these for subtitles
AUDIENCE_LANGS = {
    "🇸🇦 Arabic / عربي":"ar","🇬🇧 English":"en","🇫🇷 French / Français":"fr",
    "🇪🇸 Spanish / Español":"es","🇩🇪 German / Deutsch":"de","🇹🇷 Turkish":"tr",
    "🇮🇹 Italian":"it","🇨🇳 Chinese / 中文":"zh-CN","🇷🇺 Russian":"ru",
    "🇯🇵 Japanese / 日本語":"ja","🇧🇷 Portuguese":"pt","🇮🇳 Hindi":"hi",
    "🇰🇷 Korean":"ko","🇳🇱 Dutch":"nl","🇵🇱 Polish":"pl","🇸🇪 Swedish":"sv",
    "🇬🇷 Greek":"el","🇹🇭 Thai":"th","🇻🇳 Vietnamese":"vi",
    "🇺🇦 Ukrainian":"uk","🇮🇩 Indonesian":"id",
}

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
for k, v in {"page":"home","last_hash":None,"last_txt":"","last_lang":""}.items():
    if k not in st.session_state: st.session_state[k] = v

# URL param routing
p = st.query_params.get("page", "home")
if p in ("speaker", "audience", "home"):
    st.session_state.page = p


# ═════════════════════════════════════════════════════════════════════════════
#  H O M E   (compact — two big buttons, done)
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    components.html(PALETTE + """
<style>
body{
  min-height:100vh;display:flex;flex-direction:column;
  align-items:center;justify-content:center;
  padding:32px 20px 40px;overflow-x:hidden;gap:0;
}

/* top flag bar */
body::before{content:'';position:fixed;top:0;left:0;right:0;height:4px;z-index:99;
  background:linear-gradient(90deg,var(--red) 25%,var(--bg) 25%,var(--bg) 50%,
  var(--green) 50%,var(--green) 75%,var(--bg) 75%);}

/* brand */
.brand{text-align:center;margin-bottom:10px;}
.b-live{display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(56px,10vw,110px);line-height:.82;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--rl) 0%,var(--melon) 55%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.b-trans{display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(56px,10vw,110px);line-height:.82;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--gl) 0%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.b-sub{font-size:11px;color:#3a3a3a;letter-spacing:.2em;text-transform:uppercase;
  margin-top:10px;margin-bottom:28px;}

/* flag stripe */
.flag{display:flex;height:3px;width:100%;max-width:560px;
  border-radius:2px;overflow:hidden;margin:0 auto 32px;}
.f1{flex:1;background:#282828;}.f2{flex:1;background:#383838;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}

/* role grid */
.grid{display:flex;gap:16px;justify-content:center;flex-wrap:wrap;
  max-width:640px;width:100%;}

.card{flex:1;min-width:220px;max-width:290px;background:var(--card);
  border:1px solid var(--b);border-radius:20px;padding:28px 22px 24px;
  display:block;position:relative;overflow:hidden;
  transition:transform .25s,box-shadow .25s,border-color .25s;}
.card:hover{transform:translateY(-4px);border-color:#333;}
.card.spk:hover{box-shadow:0 16px 48px rgba(206,17,38,.22);}
.card.aud:hover{box-shadow:0 16px 48px rgba(0,122,61,.22);}

.card::before{content:'';position:absolute;width:200px;height:200px;
  border-radius:50%;top:-60px;left:-60px;pointer-events:none;}
.card.spk::before{background:radial-gradient(circle,rgba(206,17,38,.18) 0%,transparent 70%);}
.card.aud::before{background:radial-gradient(circle,rgba(0,122,61,.18) 0%,transparent 70%);}

.c-icon{font-size:44px;display:block;margin-bottom:12px;}
.c-name{font-family:'Bebas Neue',sans-serif;font-size:34px;letter-spacing:.06em;margin-bottom:8px;}
.c-name.spk{color:var(--rl);}.c-name.aud{color:var(--gl);}
.c-desc{font-size:13px;color:#4a4a4a;line-height:1.65;margin-bottom:18px;}
.c-btn{display:inline-block;padding:9px 20px;border-radius:7px;
  font-weight:700;font-size:11px;letter-spacing:.1em;text-transform:uppercase;}
.c-btn.spk{background:rgba(206,17,38,.12);color:var(--rl);border:1px solid rgba(206,17,38,.3);}
.c-btn.aud{background:rgba(0,122,61,.12);color:var(--gl);border:1px solid rgba(0,122,61,.3);}

.footer{font-size:10px;color:#232323;letter-spacing:.08em;text-align:center;margin-top:28px;}
</style>

<div class="brand">
  <span class="b-live">LIVE</span>
  <span class="b-trans">TRANSLATE</span>
  <div class="b-sub">Real-time multilingual conference subtitles &nbsp;🇵🇸</div>
</div>

<div class="flag"><div class="f1"></div><div class="f2"></div><div class="f3"></div><div class="f4"></div></div>

<div class="grid">
  <a class="card spk" href="?page=speaker">
    <span class="c-icon">🎤</span>
    <div class="c-name spk">SPEAKER</div>
    <div class="c-desc">You are presenting.<br>
      Choose your language, record your speech, and broadcast it live.</div>
    <span class="c-btn spk">I am the Speaker &rarr;</span>
  </a>
  <a class="card aud" href="?page=audience">
    <span class="c-icon">👥</span>
    <div class="c-name aud">AUDIENCE</div>
    <div class="c-desc">You are listening.<br>
      Pick your language and read live translated subtitles.</div>
    <span class="c-btn aud">I am Audience &rarr;</span>
  </a>
</div>

<div class="footer">Made with 🇵🇸 &nbsp;·&nbsp; 100% free &nbsp;·&nbsp; faster-whisper &nbsp;·&nbsp; deep-translator</div>
""", height=580, scrolling=False)

    # Streamlit buttons as fallback (href navigation is blocked inside iframe)
    c1, _, c2 = st.columns([1, .1, 1])
    with c1:
        if st.button("🎤  Enter as Speaker", use_container_width=True):
            st.session_state.page = "speaker"
            st.query_params["page"] = "speaker"
            st.rerun()
    with c2:
        if st.button("👥  Enter as Audience", use_container_width=True):
            st.session_state.page = "audience"
            st.query_params["page"] = "audience"
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  S P E A K E R
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    # ── Header ────────────────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{background:var(--bg);padding:28px 28px 0;}
body::before{content:'';position:fixed;top:0;left:0;right:0;height:4px;z-index:99;
  background:linear-gradient(90deg,var(--red) 25%,var(--bg) 25%,var(--bg) 50%,
  var(--green) 50%,var(--green) 75%,var(--bg) 75%);}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(56px,9vw,100px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--melon) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:12px;color:#3a3a3a;letter-spacing:.18em;text-transform:uppercase;margin-top:8px;}
.flag{display:flex;height:4px;border-radius:2px;overflow:hidden;margin:18px 0 0;}
.f1{flex:1;background:#282828;}.f2{flex:1;background:#383838;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}
</style>
<div class="title">SPEAK<br>NOW</div>
<div class="sub">Choose your language &nbsp;·&nbsp; Record &nbsp;·&nbsp; Broadcast live</div>
<div class="flag"><div class="f1"></div><div class="f2"></div>
  <div class="f3"></div><div class="f4"></div></div>
""", height=170, scrolling=False)

    cb, _, cback = st.columns([3, 1, 1])
    with cback:
        if st.button("← Home", use_container_width=True, key="spk_home"):
            st.session_state.page = "home"
            st.query_params["page"] = "home"
            st.rerun()

    # ── Language selector ─────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{background:transparent;padding:4px 0 2px;}
.lbl{font-size:11px;color:#3a3a3a;letter-spacing:.14em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:6px;}
</style>
<div class="lbl">🌐 &nbsp; Speaker language — choose before recording</div>
""", height=34, scrolling=False)

    spk_lang_label = st.selectbox(
        "Speaker language",
        list(SPEAKER_LANGS.keys()),
        index=0,
        label_visibility="collapsed",
        key="spk_lang_sel"
    )
    spk_lang_code = SPEAKER_LANGS[spk_lang_label]

    # ── Native recorder (the ONLY recorder — JS postMessage doesn't work in Streamlit) ─
    components.html(PALETTE + """
<style>
body{background:transparent;padding:6px 0 2px;}
.lbl{font-size:11px;color:#3a3a3a;letter-spacing:.14em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:4px;}
</style>
<div class="lbl">🎙️ &nbsp; Tap the mic to start · tap again to stop &amp; transcribe</div>
""", height=32, scrolling=False)

    rec = st.audio_input("Record", key="mic_fb", label_visibility="collapsed")

    if rec:
        b = rec.read(); h = hash(b)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            with st.spinner(f"🧠 Transcribing in {spk_lang_label}…"):
                txt, lang = transcribe(b, spk_lang_code)
            if txt:
                db_save(txt, lang)
                st.session_state.last_txt  = txt
                st.session_state.last_lang = lang
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("⚠️ No speech detected — try speaking louder or closer to the mic.")

    # ── Session status + Clear ────────────────────────────────────────────────
    n = db_count(); rows = db_all(60)
    ch1, ch2 = st.columns([4, 1])
    with ch1:
        components.html(f"""<style>
          @keyframes dp{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.75);}}}}
          body{{margin:0;padding:4px 0;background:transparent;}}
          </style>
          <div style='display:flex;align-items:center;gap:10px;
          padding:10px 16px;background:#101010;border:1px solid #222;
          border-radius:10px;font-size:13px;font-family:monospace;'>
          <span style='width:9px;height:9px;border-radius:50%;background:#00c65e;
          box-shadow:0 0 0 4px rgba(0,198,94,.18);display:inline-block;
          animation:dp 1.4s infinite;'></span>
          <span style='color:#f2ede3;'>Session: <b>{n}</b> segment(s) &nbsp;·&nbsp;
          Speaking in <b>{spk_lang_code.upper()}</b></span>
          </div>""", height=50, scrolling=False)
    with ch2:
        if st.button("🗑️ Clear", use_container_width=True, key="cl"):
            db_clear(); st.cache_data.clear()
            st.session_state.last_txt = ""
            st.rerun()

    # ── Broadcast history ─────────────────────────────────────────────────────
    if not rows:
        components.html(PALETTE + """<style>body{background:transparent;padding:20px;
          text-align:center;color:#2a2a2a;font-family:'Cairo',sans-serif;}</style>
          <div style='font-size:48px;margin-bottom:12px'>🎙️</div>
          <div style='font-size:15px;color:#3a3a3a;'>
          Nothing broadcast yet — tap the mic above and speak</div>
          """, height=120)
    else:
        cards_html = ""
        for i, (txt, lang, ts) in enumerate(rows):
            is_new  = (i == 0)
            border  = "border-left:3px solid #fd6b4b;" if is_new else ""
            bg      = "background:linear-gradient(135deg,rgba(253,107,75,.06),#161616 55%);" if is_new else ""
            anim    = "animation:slid .4s ease;" if is_new else ""
            new_tag = '<span class="ntag">NEW</span>' if is_new else ""
            cards_html += f"""
<div class="hc" style="{border}{bg}{anim}">
  <div class="meta">
    <span class="ts">🕐 {ts}</span>
    <span class="ltag">{lang.upper()}</span>
    {new_tag}
  </div>
  <div class="txt">{txt}</div>
</div>"""

        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 20px;}}
@keyframes slid{{from{{opacity:.2;transform:translateY(-8px);}}to{{opacity:1;transform:translateY(0);}}}}
.hc{{background:#161616;border:1px solid #222;border-radius:14px;
  padding:18px 22px;margin:8px 0;transition:border-color .2s;}}
.hc:hover{{border-color:#333;}}
.meta{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:10px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#2e2e2e;}}
.ltag{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);
  border-radius:4px;padding:2px 9px;font-size:10px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ntag{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);
  border-radius:4px;padding:2px 9px;font-size:10px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.txt{{font-size:18px;font-weight:600;color:#f2ede3;line-height:1.6;direction:auto;}}
</style>
{cards_html}
""", height=min(90 + len(rows) * 100, 2400), scrolling=True)


# ═════════════════════════════════════════════════════════════════════════════
#  A U D I E N C E
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    # Header
    components.html(PALETTE + """
<style>
body{background:transparent;padding:28px 28px 0;}
body::before{content:'';position:fixed;top:0;left:0;right:0;height:4px;z-index:99;
  background:linear-gradient(90deg,var(--red) 25%,var(--bg) 25%,var(--bg) 50%,
  var(--green) 50%,var(--green) 75%,var(--bg) 75%);}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(56px,9vw,100px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--gl) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:12px;color:#3a3a3a;letter-spacing:.18em;text-transform:uppercase;margin-top:8px;}
.flag{display:flex;height:4px;border-radius:2px;overflow:hidden;margin:18px 0 0;}
.f1{flex:1;background:#282828;}.f2{flex:1;background:#383838;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}
</style>
<div class="title">LIVE<br>SUBTITLES</div>
<div class="sub">Choose your language — updated every few seconds</div>
<div class="flag"><div class="f1"></div><div class="f2"></div>
  <div class="f3"></div><div class="f4"></div></div>
""", height=170, scrolling=False)

    _, cback = st.columns([4, 1])
    with cback:
        if st.button("← Home", use_container_width=True, key="aud_home"):
            st.session_state.page = "home"
            st.query_params["page"] = "home"
            st.rerun()

    # Controls
    cl, cs, cr = st.columns([3, 1, 1])
    with cl:
        lc = st.selectbox("Language", list(AUDIENCE_LANGS.keys()), index=0,
                          label_visibility="collapsed")
        tgt = AUDIENCE_LANGS[lc]
    with cs:
        fpx = st.select_slider("Size", [20, 28, 36, 44, 56, 68], value=44,
                               format_func=lambda x: f"{x}px")
    with cr:
        rate = st.select_slider("Refresh", [2, 3, 5, 8], value=3,
                                format_func=lambda x: f"{x}s")

    n = db_count()
    components.html(f"""<style>
      @keyframes dp{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.75);}}}}
      body{{margin:0;padding:4px 0;background:transparent;}}
      </style>
      <div style='display:flex;align-items:center;gap:10px;
      padding:10px 16px;background:#101010;border:1px solid #222;
      border-radius:10px;font-size:13px;font-family:monospace;'>
      <span style='width:9px;height:9px;border-radius:50%;background:#00c65e;
      box-shadow:0 0 0 4px rgba(0,198,94,.18);display:inline-block;
      animation:dp 1.4s infinite;'></span>
      <span style='color:#f2ede3;'>🔴 Live — refreshing every <b>{rate}s</b> &nbsp;·&nbsp;
      <b>{n}</b> segments &nbsp;·&nbsp; <b>{tgt}</b></span>
      </div>""", height=50, scrolling=False)

    rows = db_all(30)

    if not rows:
        components.html(PALETTE + """<style>body{background:transparent;padding:40px 20px;
          text-align:center;color:#222;font-family:'Cairo',sans-serif;}</style>
          <div style='font-size:56px;margin-bottom:14px'>⏳</div>
          <div style='font-size:18px;color:#2a2a2a;'>Waiting for the speaker to start…</div>
          <div style='font-size:13px;color:#1e1e1e;margin-top:8px;'>
          Open the Speaker tab in another browser window or device</div>""", height=200)
    else:
        # ── Latest segment — BIG ──────────────────────────────────────────────
        ltxt, llang, lts = rows[0]
        ltranslated = tr(ltxt, tgt, llang)
        tb  = tgt.split("-")[0].lower()
        sb  = llang.split("-")[0].lower() if llang else "auto"
        show_orig_l = (sb != tb) and (ltxt != ltranslated)
        orig_l = f'<div class="so">{llang.upper()} · {ltxt}</div>' if show_orig_l else ""

        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0;}}
.stage{{
  background:#0d0d0d;border:1px solid #1e1e1e;border-radius:20px;
  padding:40px 36px;min-height:200px;position:relative;overflow:hidden;
  display:flex;flex-direction:column;justify-content:center;
}}
.stage::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,var(--red) 0%,#0d0d0d 30%,var(--green) 100%);}}
.stage::before{{content:'';position:absolute;width:320px;height:320px;
  border-radius:50%;bottom:-100px;right:-100px;
  background:radial-gradient(circle,rgba(0,122,61,.07) 0%,transparent 70%);pointer-events:none;}}
.so{{font-size:14px;color:#2a2a2a;font-style:italic;direction:auto;
  line-height:1.6;padding-bottom:14px;margin-bottom:14px;border-bottom:1px solid #1a1a1a;}}
.st{{color:var(--white);font-weight:700;line-height:1.45;direction:auto;
  animation:fi .5s ease;font-size:{fpx}px;}}
@keyframes fi{{from{{opacity:.2;transform:translateY(10px);}}to{{opacity:1;transform:translateY(0);}}}}
.sm{{font-family:'JetBrains Mono',monospace;font-size:11px;color:#1e1e1e;margin-top:18px;}}
</style>
<div class="stage">
  {orig_l}
  <div class="st">{ltranslated}</div>
  <div class="sm">🕐 {lts} &nbsp;·&nbsp; {llang.upper()} → {tgt.upper()}</div>
</div>
""", height=max(260, fpx * 3 + 120), scrolling=False)

        # Action buttons
        components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 8px;}}
.row{{display:flex;gap:10px;flex-wrap:wrap;}}
.btn{{background:#161616;border:1px solid #222;border-radius:9px;
  padding:10px 20px;color:#555;font-size:13px;cursor:pointer;
  transition:all .2s;font-family:'Cairo',sans-serif;font-weight:700;}}
.btn:hover{{background:#1e1e1e;color:#f2ede3;border-color:#333;}}
#cm{{color:#00c65e;font-size:12px;margin-left:4px;opacity:0;
  transition:opacity .3s;align-self:center;}}
#fs{{display:none;position:fixed;inset:0;background:#000;z-index:99999;
  align-items:center;justify-content:center;cursor:pointer;
  flex-direction:column;text-align:center;padding:40px;}}
#fs-t{{color:#f2ede3;font-weight:700;direction:auto;line-height:1.4;
  font-size:clamp(32px,7vw,90px);max-width:92%;}}
#fs-b{{position:absolute;bottom:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,#ce1126 0%,#000 30%,#007a3d 100%);}}
#fs-h{{position:absolute;bottom:22px;font-size:12px;color:#222;font-family:monospace;}}
</style>
<div class="row">
  <button class="btn" onclick="speak()">🔊 Read aloud</button>
  <button class="btn" onclick="copy()">📋 Copy</button>
  <button class="btn" onclick="openfs()">⛶ Fullscreen</button>
  <span id="cm">Copied!</span>
</div>
<div id="fs" onclick="closefs()">
  <div id="fs-t">{ltranslated}</div>
  <div id="fs-h">Tap anywhere to close</div>
  <div id="fs-b"></div>
</div>
<script>
const T={repr(ltranslated)},L="{tgt}";
function speak(){{speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(T);u.lang=L;speechSynthesis.speak(u);}}
function copy(){{navigator.clipboard.writeText(T).then(()=>{{
  const m=document.getElementById('cm');m.style.opacity='1';
  setTimeout(()=>m.style.opacity='0',2200);}});}}
function openfs(){{document.getElementById('fs').style.display='flex';}}
function closefs(){{document.getElementById('fs').style.display='none';}}
</script>
""", height=56, scrolling=False)

        # ── History: newest → oldest (skip first, already shown big) ─────────
        older = rows[1:]
        if older:
            components.html("""<style>body{margin:0;padding:0;background:transparent;}</style>
              <div style='margin:6px 0 4px;font-size:11px;color:#1e1e1e;
              font-family:monospace;letter-spacing:.1em;'>
              ─── PREVIOUS (newest → oldest) ───</div>""", height=28, scrolling=False)

            hist_html = ""
            for seg_txt, seg_lang, seg_ts in older:
                seg_tr = tr(seg_txt, tgt, seg_lang)
                sb2    = seg_lang.split("-")[0].lower() if seg_lang else "auto"
                so     = f'<div class="ao">{seg_lang.upper()} · {seg_txt}</div>' \
                         if (sb2 != tb and seg_txt != seg_tr) else ""
                hist_html += f"""
<div class="ac">
  {so}
  <div class="at">{seg_tr}</div>
  <div class="ats">🕐 {seg_ts}</div>
</div>"""

            components.html(PALETTE + f"""
<style>
body{{background:transparent;padding:2px 0 20px;}}
.ac{{background:#141414;border:1px solid #1e1e1e;border-radius:12px;
  padding:14px 20px;margin:7px 0;opacity:.55;transition:opacity .2s;}}
.ac:hover{{opacity:.82;}}
.ao{{font-size:12px;color:#252525;font-style:italic;direction:auto;margin-bottom:5px;}}
.at{{font-size:17px;font-weight:600;color:#888;direction:auto;line-height:1.5;}}
.ats{{font-size:11px;color:#1e1e1e;font-family:'JetBrains Mono',monospace;margin-top:5px;}}
</style>
{hist_html}
""", height=min(60 + len(older) * 100, 2000), scrolling=True)

    # Auto-refresh
    time.sleep(rate)
    st.rerun()
