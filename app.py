"""
LiveTranslate Conference — v6 (Mobile-first, crash-proof)
==========================================================
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
import sqlite3, os, tempfile, time
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Hide all Streamlit chrome — add mobile viewport meta tag
st.markdown("""
<style>
#MainMenu,header,footer,[data-testid="stSidebar"],[data-testid="collapsedControl"],
[data-testid="stStatusWidget"]{display:none!important;visibility:hidden!important;}
.stApp{background:#080808!important;}
.block-container{padding:0!important;max-width:100%!important;}
/* mobile: remove Streamlit default button padding */
.stButton>button{border-radius:10px!important;font-weight:700!important;}
/* kill horizontal scroll on mobile */
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
# DATABASE  — safe multi-thread SQLite
# ─────────────────────────────────────────────────────────────────────────────
DB = os.path.join(tempfile.gettempdir(), "lt_v6.db")

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    try:
        with _cx() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS seg(
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                txt  TEXT    NOT NULL,
                lang TEXT    DEFAULT '',
                ts   TEXT    NOT NULL
            )""")
            c.commit()
    except Exception as e:
        st.error(f"DB init error: {e}")

def db_save(txt, lang):
    try:
        with _cx() as c:
            c.execute("INSERT INTO seg(txt,lang,ts) VALUES(?,?,?)",
                      (txt.strip(), lang, datetime.now().strftime("%H:%M")))
            c.commit()
        return True
    except Exception:
        return False

def db_all(limit=40):
    try:
        with _cx() as c:
            return c.execute(
                "SELECT txt,lang,ts FROM seg ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    except Exception:
        return []

def db_count():
    try:
        with _cx() as c:
            return c.execute("SELECT COUNT(*) FROM seg").fetchone()[0]
    except Exception:
        return 0

def db_clear():
    try:
        with _cx() as c:
            c.execute("DELETE FROM seg"); c.commit()
    except Exception:
        pass

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# WHISPER  — cached model, explicit language (no auto-detect)
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
            language=lang_code,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        return text, lang_code
    except Exception as e:
        return "", lang_code
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def tr(text: str, target: str, source: str = "auto") -> str:
    if not text.strip():
        return text
    src = source.split("-")[0].lower() if source and source != "auto" else "auto"
    tgt = target.split("-")[0].lower()
    if src != "auto" and src == tgt:
        return text
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=src, target=target).translate(text)
        return result or text
    except Exception as e:
        return f"[translation error: {e}]"

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE LISTS
# ─────────────────────────────────────────────────────────────────────────────
SPEAKER_LANGS = {
    "🇬🇧 English":        "en",
    "🇸🇦 Arabic / عربي":  "ar",
    "🇫🇷 French":         "fr",
    "🇹🇷 Turkish":        "tr",
    "🇪🇸 Spanish":        "es",
}

AUDIENCE_LANGS = {
    "🇸🇦 Arabic / عربي": "ar", "🇬🇧 English": "en", "🇫🇷 French": "fr",
    "🇪🇸 Spanish": "es",       "🇩🇪 German": "de",  "🇹🇷 Turkish": "tr",
    "🇮🇹 Italian": "it",       "🇨🇳 Chinese": "zh-CN","🇷🇺 Russian": "ru",
    "🇯🇵 Japanese": "ja",      "🇧🇷 Portuguese": "pt","🇮🇳 Hindi": "hi",
    "🇰🇷 Korean": "ko",        "🇳🇱 Dutch": "nl",    "🇵🇱 Polish": "pl",
    "🇸🇪 Swedish": "sv",       "🇬🇷 Greek": "el",    "🇹🇭 Thai": "th",
    "🇻🇳 Vietnamese": "vi",    "🇺🇦 Ukrainian": "uk", "🇮🇩 Indonesian": "id",
}

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "page":       "home",
    "last_hash":  None,
    "last_txt":   "",
    "last_lang":  "",
    "spk_lang":   "en",
    "aud_lang":   "ar",
    "aud_fpx":    24,        # mobile-friendly default font size
    "aud_rate":   3,
    "seg_count":  0,         # track count for change detection
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# URL param routing
_pg = st.query_params.get("page", "home")
if _pg in ("speaker", "audience", "home"):
    st.session_state.page = _pg


# ═════════════════════════════════════════════════════════════════════════════
#  H O M E  — super compact, fits any phone
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    components.html(PALETTE + FLAG_BAR + """
<style>
body{
  min-height:100vh; display:flex; flex-direction:column;
  align-items:center; justify-content:center;
  padding:20px 16px 24px; gap:0;
}
/* brand */
.brand{text-align:center; margin-bottom:6px;}
.b-live{
  display:block; font-family:'Bebas Neue',sans-serif;
  font-size:clamp(48px,12vw,88px); line-height:.82; letter-spacing:.04em;
  background:linear-gradient(135deg,var(--rl) 0%,var(--melon) 55%,var(--white) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.b-trans{
  display:block; font-family:'Bebas Neue',sans-serif;
  font-size:clamp(48px,12vw,88px); line-height:.82; letter-spacing:.04em;
  background:linear-gradient(135deg,var(--gl) 0%,var(--white) 100%);
  -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text;
}
.b-sub{font-size:10px;color:#3a3a3a;letter-spacing:.18em;text-transform:uppercase;
  margin-top:8px; margin-bottom:20px;}

/* flag stripe */
.flag{display:flex;height:3px;width:100%;max-width:480px;
  border-radius:2px;overflow:hidden;margin:0 auto 20px;}
.f1{flex:1;background:#1e1e1e;}.f2{flex:1;background:#2a2a2a;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}

/* role grid — side by side, always */
.grid{
  display:grid; grid-template-columns:1fr 1fr;
  gap:12px; width:100%; max-width:480px; margin-bottom:16px;
}
.card{
  background:var(--card); border:1px solid var(--b);
  border-radius:18px; padding:20px 14px 18px;
  display:flex; flex-direction:column; align-items:center;
  text-align:center; position:relative; overflow:hidden;
  transition:transform .2s, box-shadow .2s;
  cursor:pointer;
}
.card:active{transform:scale(.97);}
.card.spk{border-color:rgba(206,17,38,.25);}
.card.aud{border-color:rgba(0,122,61,.25);}
.card.spk:hover{box-shadow:0 12px 40px rgba(206,17,38,.18);}
.card.aud:hover{box-shadow:0 12px 40px rgba(0,122,61,.18);}

.c-icon{font-size:36px; margin-bottom:8px; display:block;}
.c-name{font-family:'Bebas Neue',sans-serif;font-size:28px;letter-spacing:.06em;margin-bottom:6px;}
.c-name.spk{color:var(--rl);} .c-name.aud{color:var(--gl);}
.c-desc{font-size:11px;color:#444;line-height:1.55;margin-bottom:14px;}
.c-btn{
  display:block; width:100%; padding:10px 8px;
  border-radius:8px; font-weight:700; font-size:11px;
  letter-spacing:.08em; text-transform:uppercase; margin-top:auto;
}
.c-btn.spk{background:rgba(206,17,38,.14);color:var(--rl);border:1px solid rgba(206,17,38,.3);}
.c-btn.aud{background:rgba(0,122,61,.14);color:var(--gl);border:1px solid rgba(0,122,61,.3);}

.footer{font-size:9px;color:#1e1e1e;letter-spacing:.08em;text-align:center;}
</style>

<div class="brand">
  <span class="b-live">LIVE</span>
  <span class="b-trans">TRANSLATE</span>
  <div class="b-sub">Real-time multilingual subtitles &nbsp;🇵🇸</div>
</div>

<div class="flag"><div class="f1"></div><div class="f2"></div><div class="f3"></div><div class="f4"></div></div>

<div class="grid">
  <a class="card spk" href="?page=speaker">
    <span class="c-icon">🎤</span>
    <div class="c-name spk">SPEAKER</div>
    <div class="c-desc">Record &amp; broadcast your speech live</div>
    <span class="c-btn spk">Enter &rarr;</span>
  </a>
  <a class="card aud" href="?page=audience">
    <span class="c-icon">👥</span>
    <div class="c-name aud">AUDIENCE</div>
    <div class="c-desc">Read live translated subtitles</div>
    <span class="c-btn aud">Enter &rarr;</span>
  </a>
</div>

<div class="footer">faster-whisper &nbsp;·&nbsp; deep-translator &nbsp;·&nbsp; 100% free 🇵🇸</div>
""", height=380, scrolling=False)

    # Streamlit fallback buttons (href blocked inside iframe)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("🎤 Speaker", use_container_width=True, key="h_spk"):
            st.session_state.page = "speaker"
            st.query_params["page"] = "speaker"
            st.rerun()
    with c2:
        if st.button("👥 Audience", use_container_width=True, key="h_aud"):
            st.session_state.page = "audience"
            st.query_params["page"] = "audience"
            st.rerun()


# ═════════════════════════════════════════════════════════════════════════════
#  S P E A K E R
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    # ── Top nav ───────────────────────────────────────────────────────────────
    nav_l, nav_r = st.columns([3, 1])
    with nav_l:
        components.html(PALETTE + FLAG_BAR + """
<style>
body{padding:20px 16px 0;}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,9vw,80px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--melon) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}
</style>
<div class="title">SPEAK NOW</div>
<div class="sub">Choose language · Tap mic · Broadcast</div>
""", height=110, scrolling=False)
    with nav_r:
        st.write("")
        if st.button("← Home", use_container_width=True, key="spk_home"):
            st.session_state.page = "home"
            st.query_params["page"] = "home"
            st.rerun()

    # ── Language + share row ──────────────────────────────────────────────────
    lc, rc = st.columns([2, 1])
    with lc:
        spk_label = st.selectbox(
            "Your language",
            list(SPEAKER_LANGS.keys()),
            index=list(SPEAKER_LANGS.values()).index(
                st.session_state.get("spk_lang", "en")
            ),
            key="spk_lang_sel",
        )
        st.session_state.spk_lang = SPEAKER_LANGS[spk_label]

    # QR code for audience — shown in right column
    with rc:
        components.html(PALETTE + """
<style>
body{padding:4px 0 0;display:flex;flex-direction:column;align-items:center;}
.lbl{font-size:9px;color:#2a2a2a;letter-spacing:.12em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:4px;text-align:center;}
#qr canvas,#qr img{border-radius:6px;}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
<div class="lbl">Audience QR</div>
<div id="qr"></div>
<script>
(function(){
  const base = window.location.href.split('?')[0];
  const url  = base + '?page=audience';
  try{
    new QRCode(document.getElementById('qr'),{
      text:url, width:80, height:80,
      colorDark:'#f2ede3', colorLight:'#161616',
      correctLevel:QRCode.CorrectLevel.M
    });
  }catch(e){}
})();
</script>
""", height=106, scrolling=False)

    # ── Divider ───────────────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{padding:2px 0;}
.flag{display:flex;height:2px;border-radius:1px;overflow:hidden;}
.f1{flex:1;background:#1a1a1a;}.f2{flex:1;background:#222;}
.f3{flex:1;background:rgba(0,122,61,.4);}.f4{flex:1;background:rgba(206,17,38,.4);}
</style>
<div class="flag"><div class="f1"></div><div class="f2"></div>
  <div class="f3"></div><div class="f4"></div></div>
""", height=10, scrolling=False)

    # ── Mic recorder ─────────────────────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{padding:6px 0 2px;}
.hint{font-size:11px;color:#2e2e2e;letter-spacing:.1em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;text-align:center;}
</style>
<div class="hint">🎙️ &nbsp; Tap the mic · speak · tap again to transcribe</div>
""", height=26, scrolling=False)

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
                if db_save(txt, lang):
                    st.session_state.last_txt  = txt
                    st.session_state.last_lang = lang
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error("Failed to save — please try again.")
            else:
                st.warning("⚠️ No speech detected — speak louder or closer to the mic.")

    # ── Status bar + Clear ────────────────────────────────────────────────────
    n = db_count()
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
  <span style='color:#f2ede3;'><b>{n}</b> segment(s) &nbsp;·&nbsp;
    Speaking <b>{st.session_state.spk_lang.upper()}</b></span>
</div>""", height=46, scrolling=False)
    with sc2:
        if st.button("🗑️ Clear all", use_container_width=True, key="clr"):
            db_clear()
            st.cache_data.clear()
            st.session_state.last_txt = ""
            st.rerun()

    # ── Broadcast history ─────────────────────────────────────────────────────
    rows = db_all(60)
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
#  A U D I E N C E  — fragment-based auto-refresh (NO time.sleep = no crash)
# ═════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    # ── Top nav ───────────────────────────────────────────────────────────────
    anl, anr = st.columns([3, 1])
    with anl:
        components.html(PALETTE + FLAG_BAR + """
<style>
body{padding:20px 16px 0;}
.title{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,9vw,80px);
  line-height:.82;letter-spacing:.03em;
  background:linear-gradient(140deg,var(--white) 30%,var(--gl) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.sub{font-size:10px;color:#3a3a3a;letter-spacing:.15em;text-transform:uppercase;margin-top:6px;}
</style>
<div class="title">LIVE SUBS</div>
<div class="sub">Real-time translated subtitles</div>
""", height=110, scrolling=False)
    with anr:
        st.write("")
        if st.button("← Home", use_container_width=True, key="aud_home"):
            st.session_state.page = "home"
            st.query_params["page"] = "home"
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

    # Font size — big +/- buttons (mobile-friendly, no slider)
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

    # ── Wake Lock injected once — keeps phone screen on ───────────────────────
    components.html("""
<script>
(async function(){
  if('wakeLock' in navigator){
    try{
      await navigator.wakeLock.request('screen');
    }catch(e){}
    document.addEventListener('visibilitychange',async()=>{
      if(document.visibilityState==='visible'){
        try{await navigator.wakeLock.request('screen');}catch(e){}
      }
    });
  }
})();
</script>
""", height=0, scrolling=False)

    # ── Live subtitle display — auto-refreshing fragment (no sleep/crash) ─────
    tgt  = st.session_state.aud_lang
    fpx  = st.session_state.aud_fpx
    rate = st.session_state.aud_rate

    @st.fragment(run_every=rate)
    def live_display():
        tgt  = st.session_state.aud_lang
        fpx  = st.session_state.aud_fpx
        rows = db_all(25)
        n    = db_count()

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
    <b>{tgt.upper()}</b> &nbsp;·&nbsp; ↺{rate}s</span>
</div>""", height=40, scrolling=False)

        if not rows:
            components.html(PALETTE + """
<style>body{padding:30px 0;text-align:center;}</style>
<div style='font-size:44px;margin-bottom:10px'>⏳</div>
<div style='font-size:15px;color:#2a2a2a;'>Waiting for speaker…</div>
<div style='font-size:11px;color:#1a1a1a;margin-top:6px;'>
  Open the Speaker tab on another device</div>""", height=160)
            return

        # Latest — BIG
        ltxt, llang, lts = rows[0]
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
/* fullscreen overlay */
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
            for st_txt, sl, sts in older:
                s_tr  = tr(st_txt, tgt, sl)
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

    # Call the auto-refreshing fragment
    live_display()
