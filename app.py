"""
LiveTranslate Conference — 100% Free · Streamlit Cloud Compatible
==================================================================

ROOT CAUSE OF "NEVER RECORDS" BUG:
  Streamlit reruns the ENTIRE script on every interaction.
  This kills background threads, resets queues, and loses all state.
  The threading + sounddevice approach CANNOT work on Streamlit Cloud.

REAL SOLUTION:
  Use st.audio_input() — Streamlit's built-in browser mic widget.
  The browser itself records audio and sends it as a WAV blob.
  No sounddevice needed. No PortAudio. No threading. Works everywhere.

HOW IT WORKS:
  1. st.audio_input() opens browser mic (single click, no install)
  2. User speaks, clicks stop — WAV bytes available immediately
  3. WAV → faster-whisper with task="transcribe", language=None
     → auto-detects Arabic, French, English, etc.
  4. Transcript + detected language saved to SQLite
  5. Audience polls SQLite, deep-translator translates on-the-fly
"""

import streamlit as st
import sqlite3
import time
import os
import tempfile
from datetime import datetime

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate · Conference",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Palestine-Inspired Modern CSS ───────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
  --black:    #0d0d0d;
  --dark:     #111111;
  --surface:  #181818;
  --card:     #1e1e1e;
  --border:   #2c2c2c;
  --white:    #f0ede6;
  --muted:    #666660;
  --green:    #007a3d;
  --green-lt: #00c65e;
  --red:      #ce1126;
  --red-lt:   #ff3348;
  --amber:    #f59e0b;
}

html, body, [class*="css"] {
  font-family: 'Cairo', sans-serif !important;
  background: var(--black) !important;
  color: var(--white) !important;
}

::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--dark); }
::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

.stApp { background: var(--black) !important; }

[data-testid="stSidebar"] {
  background: var(--dark) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--white) !important; }

.hero {
  padding: 32px 0 20px;
  border-top: 3px solid transparent;
  border-image: linear-gradient(90deg, var(--red) 0%, #1a1a1a 35%, var(--green) 100%) 1;
  margin-bottom: 4px;
}
.hero-title {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(44px, 7vw, 86px) !important;
  line-height: 0.92 !important;
  margin: 0 !important;
  background: linear-gradient(140deg, var(--white) 30%, var(--green-lt) 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  letter-spacing: 0.02em;
}
.hero-sub {
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-top: 10px;
}

.flag-stripe {
  display: flex; height: 4px; border-radius: 2px; overflow: hidden; margin: 14px 0 24px;
}
.s-bk { flex:1; background:#3a3a3a; }
.s-wh { flex:1; background:#4a4a4a; }
.s-gr { flex:1; background:var(--green); }
.s-rd { flex:1; background:var(--red); }

.badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 5px 16px; border-radius: 4px;
  font-size: 11px; font-weight: 700;
  letter-spacing: 0.14em; text-transform: uppercase;
  margin-bottom: 16px;
}
.badge-spk { background:rgba(206,17,38,.1); color:var(--red-lt); border:1px solid rgba(206,17,38,.3); }
.badge-aud { background:rgba(0,122,61,.1);  color:var(--green-lt); border:1px solid rgba(0,122,61,.3); }

.sbar {
  display:flex; align-items:center; gap:12px;
  padding:13px 18px;
  background:var(--surface); border:1px solid var(--border); border-radius:8px;
  font-size:13px; font-family:'JetBrains Mono',monospace;
  margin:10px 0;
}
.dot { width:9px; height:9px; border-radius:50%; flex-shrink:0; }
.dot-idle { background:#333; }
.dot-live { background:var(--green-lt); box-shadow:0 0 0 4px rgba(0,198,94,.2);
            animation:pulse 1.4s ease-in-out infinite; }
@keyframes pulse {
  0%,100%{ opacity:1; transform:scale(1); }
  50%    { opacity:.35; transform:scale(.8); }
}

.instr-box {
  background:var(--surface);
  border:1px solid var(--border);
  border-left:3px solid var(--green);
  border-radius:8px;
  padding:16px 20px;
  margin:12px 0;
}
.step {
  display:flex; gap:14px; align-items:flex-start;
  padding:10px 0; border-bottom:1px solid #222;
}
.step:last-child { border-bottom:none; }
.step-num {
  min-width:26px; height:26px; border-radius:50%;
  background:var(--green); color:var(--white);
  display:flex; align-items:center; justify-content:center;
  font-size:12px; font-weight:700; flex-shrink:0; margin-top:2px;
}
.step-body { font-size:14px; color:#aaa; line-height:1.6; }
.step-body strong { color:var(--white); }

.tcard {
  background:var(--card);
  border:1px solid var(--border);
  border-radius:10px;
  padding:18px 22px;
  margin:8px 0;
  transition:border-color .2s;
}
.tcard:hover { border-color:#444; }
.tcard.fresh {
  border-left:3px solid var(--green-lt);
  background:linear-gradient(135deg, rgba(0,198,94,.05) 0%, var(--card) 60%);
  animation:slideIn .3s ease;
}
@keyframes slideIn {
  from { opacity:.4; transform:translateY(-6px); }
  to   { opacity:1;  transform:translateY(0); }
}
.tcard-meta {
  display:flex; align-items:center; gap:8px; flex-wrap:wrap;
  margin-bottom:10px;
}
.tcard-ts { font-family:'JetBrains Mono',monospace; font-size:11px; color:var(--muted); }
.ltag {
  background:rgba(0,198,94,.08); color:var(--green-lt);
  border:1px solid rgba(0,198,94,.2); border-radius:4px;
  padding:1px 8px; font-size:10px; font-weight:700;
  letter-spacing:.08em; text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;
}
.ltag-red {
  background:rgba(206,17,38,.08) !important; color:var(--red-lt) !important;
  border:1px solid rgba(206,17,38,.2) !important;
}
.orig-text {
  font-size:13px; color:var(--muted); font-style:italic;
  line-height:1.65; direction:auto;
  padding-bottom:10px; margin-bottom:10px;
  border-bottom:1px solid var(--border);
}
.trans-text {
  font-size:20px; font-weight:600; color:var(--white);
  line-height:1.65; direction:auto;
}

.empty-state {
  text-align:center; padding:60px 20px; color:var(--muted);
}
.empty-state .icon { font-size:52px; margin-bottom:14px; }
.empty-state p { font-size:15px; }

.stButton > button {
  background:var(--green) !important; color:var(--white) !important;
  border:none !important; border-radius:7px !important;
  font-family:'Cairo',sans-serif !important; font-weight:700 !important;
  font-size:14px !important; letter-spacing:.04em !important;
  transition:all .2s !important; padding:10px 22px !important;
}
.stButton > button:hover {
  background:#009a4d !important; transform:translateY(-1px) !important;
  box-shadow:0 4px 18px rgba(0,198,94,.22) !important;
}
.stSelectbox > div > div {
  background:var(--surface) !important; border:1px solid var(--border) !important;
  color:var(--white) !important; border-radius:8px !important;
}
.stSelectbox label, .stToggle label, .stSlider label {
  color:var(--white) !important; font-weight:600 !important;
}
hr { border-color:var(--border) !important; }
</style>
""", unsafe_allow_html=True)

# ─── Language map ─────────────────────────────────────────────────────────────
LANGUAGES = {
    "🇸🇦 Arabic / عربي":           "ar",
    "🇬🇧 English":                  "en",
    "🇫🇷 French / Français":        "fr",
    "🇪🇸 Spanish / Español":        "es",
    "🇩🇪 German / Deutsch":         "de",
    "🇹🇷 Turkish / Türkçe":         "tr",
    "🇮🇹 Italian / Italiano":       "it",
    "🇨🇳 Chinese / 中文":           "zh-CN",
    "🇷🇺 Russian / Русский":        "ru",
    "🇯🇵 Japanese / 日本語":        "ja",
    "🇧🇷 Portuguese / Português":   "pt",
    "🇮🇳 Hindi / हिन्दी":           "hi",
    "🇰🇷 Korean / 한국어":           "ko",
    "🇳🇱 Dutch / Nederlands":       "nl",
    "🇵🇱 Polish / Polski":          "pl",
    "🇸🇪 Swedish / Svenska":        "sv",
    "🇬🇷 Greek / Ελληνικά":         "el",
    "🇹🇭 Thai / ภาษาไทย":          "th",
    "🇻🇳 Vietnamese / Tiếng Việt":  "vi",
    "🇺🇦 Ukrainian / Українська":   "uk",
    "🇮🇩 Indonesian / Bahasa":      "id",
}

# ─── SQLite shared state ──────────────────────────────────────────────────────
DB_PATH = os.path.join(tempfile.gettempdir(), "livetranslate_v2.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                original      TEXT NOT NULL,
                detected_lang TEXT NOT NULL DEFAULT '',
                timestamp     TEXT NOT NULL
            )
        """)
        conn.commit()

def save_segment(text: str, lang: str):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO segments (original, detected_lang, timestamp) VALUES (?,?,?)",
            (text.strip(), lang, datetime.now().strftime("%H:%M:%S")),
        )
        conn.commit()

def get_segments(limit: int = 20):
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            "SELECT id, original, detected_lang, timestamp FROM segments ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return list(reversed(rows))

def get_segment_count() -> int:
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute("SELECT COUNT(*) FROM segments").fetchone()[0]

def clear_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM segments")
        conn.commit()

init_db()

# ─── Whisper model (cached permanently for the session) ──────────────────────
@st.cache_resource(show_spinner=False)
def load_whisper_model():
    """
    Load faster-whisper ONCE — cached forever in the session.
    Tries GPU (float16) first, falls back to CPU (int8).
    Returns (model, info_string).
    """
    try:
        from faster_whisper import WhisperModel
        try:
            m = WhisperModel("base", device="cuda", compute_type="float16")
            return m, "faster-whisper · base · GPU ✅"
        except Exception:
            m = WhisperModel("base", device="cpu", compute_type="int8")
            return m, "faster-whisper · base · CPU ✅"
    except ImportError:
        return None, "❌ faster-whisper not installed — pip install faster-whisper"
    except Exception as e:
        return None, f"❌ Error: {e}"

# ─── Translation (cached per text+lang pair for 2 hours) ─────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def translate(text: str, target: str, source: str = "auto") -> str:
    """
    Translate via deep-translator (Google Translate, free, no key).
    source = ISO language code detected by Whisper (e.g. 'ar', 'fr').
    """
    if not text.strip():
        return text
    src_base = source.split("-")[0].lower() if source and source != "auto" else "auto"
    tgt_base = target.split("-")[0].lower()
    if src_base != "auto" and src_base == tgt_base:
        return text   # same language — skip translation
    try:
        from deep_translator import GoogleTranslator
        result = GoogleTranslator(source=src_base, target=target).translate(text)
        return result or text
    except Exception as e:
        return f"[Translation error: {e}]"

# ─── Core transcription function ─────────────────────────────────────────────
def transcribe_audio(audio_bytes: bytes) -> tuple:
    """
    Transcribe WAV bytes using faster-whisper.
    Returns (transcript_text, detected_language_code).

    CRITICAL SETTINGS:
      task="transcribe" → keeps original language (NOT forced-to-English translate)
      language=None     → fully automatic language detection
      beam_size=5       → good accuracy balance
      vad_filter=True   → skips silent parts (faster + cleaner output)
    """
    model, info = load_whisper_model()
    if model is None:
        return "", "err"

    # Write to temp WAV file (faster-whisper needs a file path, not bytes)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name

    try:
        segments_iter, meta = model.transcribe(
            tmp_path,
            task="transcribe",           # keep original language
            language=None,               # auto-detect any of 99 languages
            beam_size=5,
            best_of=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        # Consume the generator to get all text
        text_parts = []
        for seg in segments_iter:
            text_parts.append(seg.text.strip())
        text = " ".join(text_parts).strip()
        detected = meta.language  # 'ar', 'fr', 'en', 'zh', etc.
        return text, detected
    except Exception as e:
        return f"[Transcription error: {e}]", "err"
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

# ─── Session state defaults ───────────────────────────────────────────────────
for k, v in {
    "last_transcript": "",
    "last_lang":       "",
    "last_audio_hash": None,
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='text-align:center;padding:18px 0 10px'>
      <div style='font-family:Bebas Neue,sans-serif;font-size:28px;
        background:linear-gradient(135deg,#f0ede6,#00c65e);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
        background-clip:text;letter-spacing:.06em;'>LIVETRANSLATE</div>
      <div style='font-size:10px;color:#444;letter-spacing:.14em;
        text-transform:uppercase;margin-top:3px;'>Conference Edition</div>
    </div>
    <div class="flag-stripe">
      <div class="s-bk"></div><div class="s-wh"></div>
      <div class="s-gr"></div><div class="s-rd"></div>
    </div>
    """, unsafe_allow_html=True)

    role = st.radio("**Your Role**", ["🎤 Speaker", "👥 Audience"])

    st.divider()

    _, winfo = load_whisper_model()
    n_segs = get_segment_count()
    st.markdown(f"""
    <div style='font-size:11px;font-family:JetBrains Mono,monospace;
      color:#555;padding:4px 0;line-height:2;'>
      🧠 {winfo}<br>
      📦 Segments: {n_segs}
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    if st.button("🗑️ Clear all segments", use_container_width=True):
        clear_db()
        st.cache_data.clear()
        st.session_state.last_transcript = ""
        st.session_state.last_lang = ""
        st.rerun()

    st.markdown("""
    <div style='font-size:11px;color:#2a2a2a;margin-top:16px;line-height:1.9;'>
      🇵🇸 Palestine colour theme<br>
      ✅ 100% free · No API key<br>
      🧠 faster-whisper (local AI)<br>
      🌐 deep-translator (Google)
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  SPEAKER VIEW
# ═══════════════════════════════════════════════════════════════════════════════
if role == "🎤 Speaker":

    st.markdown("""
    <div class="hero">
      <div class="hero-title">SPEAK<br>NOW</div>
      <div class="hero-sub">تحدث الآن · Parlez maintenant · Speak now · Habla ahora</div>
    </div>
    <div class="flag-stripe">
      <div class="s-bk"></div><div class="s-wh"></div>
      <div class="s-gr"></div><div class="s-rd"></div>
    </div>
    <span class="badge badge-spk">🎤 SPEAKER MODE</span>
    """, unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### 🎙️ Record & Broadcast")

        # Clear step-by-step instructions
        st.markdown("""
        <div class="instr-box">
          <div class="step">
            <div class="step-num">1</div>
            <div class="step-body">
              Click the <strong>microphone icon</strong> below to start recording
            </div>
          </div>
          <div class="step">
            <div class="step-num">2</div>
            <div class="step-body">
              <strong>Speak</strong> in any language — Arabic, French, Spanish, English…<br>
              Language is detected <strong>automatically</strong>
            </div>
          </div>
          <div class="step">
            <div class="step-num">3</div>
            <div class="step-body">
              Click <strong>stop</strong> (square icon) when done with your sentence
            </div>
          </div>
          <div class="step">
            <div class="step-num">4</div>
            <div class="step-body">
              Click <strong>▶ BROADCAST</strong> to send it live to the audience
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ═══════════════════════════════════════════════════════════════════
        #  MICROPHONE WIDGET
        #  st.audio_input() = Streamlit native browser recording.
        #  Works on Streamlit Cloud WITHOUT sounddevice/PortAudio.
        #  Returns a BytesIO-like object when the user stops recording.
        # ═══════════════════════════════════════════════════════════════════
        recorded = st.audio_input(
            "🎙️ Click mic to record — speak — click stop",
            key="mic_widget",
        )

        if recorded is not None:
            # Read bytes once
            audio_bytes = recorded.read()
            audio_hash = hash(audio_bytes)

            # Show audio player so speaker can hear what they recorded
            st.audio(recorded, format="audio/wav")

            if audio_hash == st.session_state.last_audio_hash:
                # Already processed this exact recording
                st.info("☝️ This segment was already broadcast. Record a new one above.")
            else:
                # New recording — show broadcast button
                if st.button("▶ BROADCAST THIS SEGMENT", use_container_width=True):
                    st.session_state.last_audio_hash = audio_hash

                    with st.spinner("🧠 Transcribing… AI detecting language automatically"):
                        text, lang = transcribe_audio(audio_bytes)

                    if text and not text.startswith("["):
                        save_segment(text, lang)
                        st.session_state.last_transcript = text
                        st.session_state.last_lang = lang
                        st.cache_data.clear()

                        st.markdown(f"""
                        <div class="tcard fresh">
                          <div class="tcard-meta">
                            <span class="ltag">✅ BROADCASTED</span>
                            <span class="ltag">DETECTED: {lang.upper()}</span>
                            <span class="tcard-ts">{datetime.now().strftime('%H:%M:%S')}</span>
                          </div>
                          <div class="trans-text">{text}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        st.success(f"✅ Sent live! Language detected: **{lang}**")
                    else:
                        st.warning(
                            "⚠️ No speech detected.\n\n"
                            "**Try:**\n"
                            "- Speak louder or closer to the mic\n"
                            "- Check your browser mic permissions\n"
                            "- Record for at least 2 seconds"
                        )

        # Dependency check expander
        with st.expander("📦 Package status", expanded=False):
            for name, mod in [
                ("faster-whisper", "faster_whisper"),
                ("deep-translator", "deep_translator"),
                ("numpy", "numpy"),
            ]:
                try:
                    __import__(mod)
                    st.markdown(f"✅ `{name}`")
                except ImportError:
                    st.markdown(f"❌ `{name}` — `pip install {name}`")
            st.info("ℹ️ `sounddevice` is **NOT needed** — we use the browser mic widget.")

    with col_right:
        st.markdown("### 📡 Broadcast History")

        if st.session_state.last_transcript:
            st.markdown(f"""
            <div class="tcard fresh">
              <div class="tcard-meta">
                <span class="ltag ltag-red">🔴 LAST SENT</span>
                <span class="ltag">LANG: {st.session_state.last_lang.upper()}</span>
              </div>
              <div class="trans-text">{st.session_state.last_transcript}</div>
            </div>
            """, unsafe_allow_html=True)

        segs = get_segments(12)
        if not segs:
            st.markdown("""
            <div class="empty-state">
              <div class="icon">🎙️</div>
              <p>Nothing broadcast yet.<br>Record a segment and click BROADCAST.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            for seg in reversed(segs):
                sid, original, det_lang, ts = seg
                st.markdown(f"""
                <div class="tcard">
                  <div class="tcard-meta">
                    <span class="tcard-ts">🕐 {ts}</span>
                    <span class="ltag">{det_lang.upper() if det_lang else '?'}</span>
                  </div>
                  <div class="orig-text">{original}</div>
                </div>
                """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  AUDIENCE VIEW
# ═══════════════════════════════════════════════════════════════════════════════
else:
    st.markdown("""
    <div class="hero">
      <div class="hero-title">LIVE<br>SUBTITLES</div>
      <div class="hero-sub">Real-time translation · Select your language below</div>
    </div>
    <div class="flag-stripe">
      <div class="s-bk"></div><div class="s-wh"></div>
      <div class="s-gr"></div><div class="s-rd"></div>
    </div>
    <span class="badge badge-aud">👥 AUDIENCE MODE</span>
    """, unsafe_allow_html=True)

    ctrl_l, ctrl_r = st.columns([2, 1], gap="large")
    with ctrl_l:
        lang_choice = st.selectbox(
            "🌐 **Translate into:**",
            list(LANGUAGES.keys()),
            index=0,
        )
        target_lang = LANGUAGES[lang_choice]

    with ctrl_r:
        st.markdown("<br>", unsafe_allow_html=True)
        live = st.toggle("🔴 Auto-refresh", value=True)
        rate = st.select_slider(
            "Refresh every",
            options=[2, 3, 5, 8, 15],
            value=3,
            format_func=lambda x: f"{x}s",
            disabled=not live,
        )

    n = get_segment_count()
    st.markdown(f"""
    <div class="sbar">
      <div class="dot {'dot-live' if live else 'dot-idle'}"></div>
      <div>
        {'🔴 Live — refreshing every ' + str(rate) + 's' if live else '⏸ Paused'}
        &nbsp;·&nbsp; <b>{n}</b> segment(s) received
        &nbsp;·&nbsp; Target: <b>{target_lang}</b>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    segs = get_segments(20)
    if not segs:
        st.markdown("""
        <div class="empty-state">
          <div class="icon">⏳</div>
          <p>Waiting for the speaker to broadcast…<br>
          <small style='color:#333;'>Open the Speaker tab in another browser window or device.</small></p>
        </div>
        """, unsafe_allow_html=True)
    else:
        for i, seg in enumerate(reversed(segs)):
            sid, original, det_lang, ts = seg

            # Translate (free Google, cached)
            translated = translate(original, target_lang, det_lang)

            is_fresh = (i == 0)
            card_cls = "tcard fresh" if is_fresh else "tcard"

            tgt_base = target_lang.split("-")[0].lower()
            src_base = det_lang.split("-")[0].lower() if det_lang else "auto"
            show_orig = (src_base != tgt_base) and (original != translated)

            orig_html = ""
            if show_orig:
                orig_html = f'<div class="orig-text">{det_lang.upper() if det_lang else "?"} · {original}</div>'

            fresh_tag = '<span class="ltag ltag-red">NEW</span>' if is_fresh else ""

            st.markdown(f"""
            <div class="{card_cls}">
              <div class="tcard-meta">
                <span class="tcard-ts">🕐 {ts}</span>
                <span class="ltag">{det_lang.upper() if det_lang else '?'} → {target_lang.upper()}</span>
                {fresh_tag}
              </div>
              {orig_html}
              <div class="trans-text">{translated}</div>
            </div>
            """, unsafe_allow_html=True)

    # Auto-refresh loop
    if live:
        time.sleep(rate)
        st.rerun()
