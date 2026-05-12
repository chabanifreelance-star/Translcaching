"""
LiveTranslate Conference — 100% Free Multilingual Real-Time Translation
=======================================================================
Architecture:
  - Streamlit frontend with Palestine-inspired theme
  - faster-whisper (local, CPU/GPU) for multilingual transcription
  - deep-translator (Google Translate, free) for translation
  - sounddevice + numpy for microphone capture
  - Silence detection via RMS energy threshold
  - Threading for non-blocking audio capture
  - SQLite for shared state between Speaker and Audience pages

Flow:
  1. Speaker starts listening → audio captured in chunks via sounddevice
  2. Each chunk's RMS is checked; 3s of silence triggers segment flush
  3. Accumulated audio written to temp WAV → fed to WhisperModel
  4. Whisper auto-detects language and transcribes in original language
  5. Transcript saved to SQLite with detected language tag
  6. Audience page polls DB every N seconds, translates on-the-fly
  7. Streamlit st.rerun() drives the refresh loop
"""

import streamlit as st
import sqlite3
import time
import os
import threading
import queue
import tempfile
import wave
import numpy as np
from datetime import datetime

# ─── Page Config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LiveTranslate · Conference",
    page_icon="🌐",
    layout="wide",
    initial_sidebar_ebar_state="expanded",
)

# ─── Palestine-Inspired Modern Theme ────────────────────────────────────────
THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

/* ── Palette ──
   Black  : #0d0d0d / #111111 / #1a1a1a
   White  : #f5f5f0 / #e8e8e0
   Green  : #007a3d  (Palestinian flag green)
   Red    : #ce1126  (Palestinian flag red)
   Accent : #00c65e  (bright green glow)
*/

:root {
  --black:    #0d0d0d;
  --dark:     #111111;
  --surface:  #1a1a1a;
  --border:   #2a2a2a;
  --white:    #f5f5f0;
  --muted:    #7a7a70;
  --green:    #007a3d;
  --green-lt: #00c65e;
  --red:      #ce1126;
  --red-lt:   #ff2d47;
}

html, body, [class*="css"] {
  font-family: 'Cairo', sans-serif !important;
  background: var(--black) !important;
  color: var(--white) !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 4px; }
::-webkit-scrollbar-track { background: var(--dark); }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

/* App background */
.stApp { background: var(--black) !important; }

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--dark) !important;
  border-right: 1px solid var(--border) !important;
}
[data-testid="stSidebar"] * { color: var(--white) !important; }
[data-testid="stSidebar"] .stRadio label { font-weight: 600; }

/* Header hero */
.hero-header {
  position: relative;
  padding: 40px 0 30px;
  margin-bottom: 8px;
  overflow: hidden;
}
.hero-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--red), var(--black) 30%, var(--green));
}
.hero-title {
  font-family: 'Bebas Neue', sans-serif !important;
  font-size: clamp(42px, 6vw, 80px) !important;
  letter-spacing: 0.04em;
  line-height: 1 !important;
  margin: 0 !important;
  background: linear-gradient(135deg, var(--white) 40%, var(--green-lt));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-sub {
  font-size: 13px;
  color: var(--muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-top: 8px;
  font-weight: 400;
}

/* Flag stripe decoration */
.flag-stripe {
  display: flex;
  height: 5px;
  width: 100%;
  margin: 16px 0;
  border-radius: 3px;
  overflow: hidden;
  gap: 2px;
}
.stripe-black { flex: 1; background: #3a3a3a; }
.stripe-white { flex: 1; background: #555; }
.stripe-green { flex: 1; background: var(--green); }
.stripe-red   { flex: 1; background: var(--red); }

/* Role badges */
.role-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 18px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  margin-bottom: 10px;
}
.role-speaker {
  background: rgba(206,17,38,0.12);
  color: var(--red-lt);
  border: 1px solid rgba(206,17,38,0.35);
}
.role-audience {
  background: rgba(0,122,61,0.12);
  color: var(--green-lt);
  border: 1px solid rgba(0,122,61,0.35);
}

/* Recording status */
.rec-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin: 12px 0;
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
}
.rec-dot {
  width: 10px; height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}
.rec-dot.active {
  background: var(--red-lt);
  box-shadow: 0 0 0 4px rgba(206,17,38,0.2);
  animation: rec-pulse 1.2s ease-in-out infinite;
}
.rec-dot.idle { background: var(--border); }
.rec-dot.processing {
  background: #f59e0b;
  box-shadow: 0 0 0 4px rgba(245,158,11,0.2);
  animation: rec-pulse 0.6s ease-in-out infinite;
}
@keyframes rec-pulse {
  0%,100% { opacity: 1; transform: scale(1); }
  50%      { opacity: 0.4; transform: scale(0.85); }
}

/* Subtitle cards */
.subtitle-card {
  position: relative;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 22px;
  margin: 8px 0;
  transition: border-color 0.25s;
}
.subtitle-card:hover { border-color: #444; }
.subtitle-card.latest {
  border-left: 3px solid var(--green);
  background: linear-gradient(135deg, rgba(0,122,61,0.06), var(--surface));
}
.subtitle-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}
.subtitle-meta .ts {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--muted);
}
.lang-tag {
  background: rgba(0,198,94,0.1);
  color: var(--green-lt);
  border: 1px solid rgba(0,198,94,0.25);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  font-family: 'JetBrains Mono', monospace;
}
.original-text {
  font-size: 14px;
  color: var(--muted);
  font-style: italic;
  margin-bottom: 10px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--border);
  line-height: 1.65;
  direction: auto;
}
.translated-text {
  font-size: 20px;
  font-weight: 600;
  color: var(--white);
  line-height: 1.6;
  direction: auto;
}

/* Audio level bar */
.level-container {
  display: flex;
  align-items: center;
  gap: 3px;
  height: 28px;
  margin: 4px 0;
}
.level-bar {
  width: 4px;
  border-radius: 2px;
  background: var(--green);
  transition: height 0.12s ease;
  min-height: 4px;
}

/* Waiting state */
.waiting-box {
  text-align: center;
  padding: 70px 30px;
  color: var(--border);
}
.waiting-box .big-icon { font-size: 56px; margin-bottom: 16px; }
.waiting-box p { font-size: 15px; color: var(--muted); }

/* Stats row */
.stats-row {
  display: flex;
  gap: 12px;
  margin: 16px 0;
  flex-wrap: wrap;
}
.stat-chip {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 16px;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--muted);
}
.stat-chip span { color: var(--white); font-weight: 600; }

/* Silence meter */
.silence-bar-wrap {
  background: var(--border);
  border-radius: 3px;
  height: 4px;
  margin: 6px 0;
  overflow: hidden;
}
.silence-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, var(--green), var(--red));
  transition: width 0.3s linear;
}

/* Streamlit overrides */
.stButton > button {
  background: var(--green) !important;
  color: var(--white) !important;
  border: none !important;
  border-radius: 6px !important;
  font-family: 'Cairo', sans-serif !important;
  font-weight: 700 !important;
  font-size: 14px !important;
  letter-spacing: 0.04em !important;
  padding: 10px 20px !important;
  transition: all 0.2s !important;
}
.stButton > button:hover {
  background: #009a4d !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 16px rgba(0,198,94,0.25) !important;
}
button[kind="secondary"] {
  background: var(--red) !important;
}
button[kind="secondary"]:hover {
  background: #a80e1e !important;
}

.stSelectbox > div > div {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  color: var(--white) !important;
  border-radius: 8px !important;
}
.stSelectbox label { color: var(--white) !important; font-weight: 600 !important; }

.stToggle label { color: var(--white) !important; }

.stSlider > div > div { color: var(--white) !important; }
[data-testid="stSlider"] .st-ae { background: var(--green) !important; }

.stAlert { border-radius: 8px !important; }
div[data-testid="stNotification"] { border-radius: 8px !important; }

hr { border-color: var(--border) !important; }
</style>
"""
st.markdown(THEME_CSS, unsafe_allow_html=True)

# ─── Language Map ─────────────────────────────────────────────────────────────
LANGUAGES = {
    "🇸🇦 Arabic": "ar",
    "🇬🇧 English": "en",
    "🇫🇷 French": "fr",
    "🇪🇸 Spanish": "es",
    "🇩🇪 German": "de",
    "🇹🇷 Turkish": "tr",
    "🇮🇹 Italian": "it",
    "🇨🇳 Chinese": "zh-CN",
    "🇷🇺 Russian": "ru",
    "🇯🇵 Japanese": "ja",
    "🇧🇷 Portuguese": "pt",
    "🇮🇳 Hindi": "hi",
    "🇰🇷 Korean": "ko",
    "🇳🇱 Dutch": "nl",
    "🇵🇱 Polish": "pl",
    "🇸🇪 Swedish": "sv",
    "🇬🇷 Greek": "el",
    "🇹🇭 Thai": "th",
    "🇻🇳 Vietnamese": "vi",
    "🇺🇦 Ukrainian": "uk",
    "🇮🇩 Indonesian": "id",
    "🇵🇸 Palestinian Arabic": "ar",
}

LANG_DISPLAY = {v: k for k, v in LANGUAGES.items()}

# ─── Database ─────────────────────────────────────────────────────────────────
DB_PATH = os.path.join(tempfile.gettempdir(), "livetranslate_conf.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            original     TEXT    NOT NULL,
            detected_lang TEXT   NOT NULL DEFAULT 'unknown',
            timestamp    TEXT    NOT NULL
        )
    """)
    # status table for speaker state
    c.execute("""
        CREATE TABLE IF NOT EXISTS speaker_status (
            id     INTEGER PRIMARY KEY CHECK (id=1),
            state  TEXT NOT NULL DEFAULT 'idle',
            updated TEXT NOT NULL DEFAULT ''
        )
    """)
    c.execute("INSERT OR IGNORE INTO speaker_status(id,state,updated) VALUES(1,'idle','')")
    conn.commit()
    conn.close()

def save_segment(text: str, lang: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO segments (original, detected_lang, timestamp) VALUES (?,?,?)",
        (text.strip(), lang, datetime.now().strftime("%H:%M:%S")),
    )
    conn.commit()
    conn.close()

def get_segments(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, original, detected_lang, timestamp FROM segments ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = c.fetchall()
    conn.close()
    return list(reversed(rows))

def get_segment_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM segments")
    n = c.fetchone()[0]
    conn.close()
    return n

def clear_segments():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM segments")
    conn.commit()
    conn.close()

def set_speaker_state(state: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "UPDATE speaker_status SET state=?, updated=? WHERE id=1",
        (state, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def get_speaker_state() -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT state FROM speaker_status WHERE id=1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else "idle"

init_db()

# ─── Translation (deep-translator, free) ─────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def translate_text(text: str, target_lang: str, source_lang: str = "auto") -> str:
    """
    Translate text using deep-translator (Google Translate backend, free).
    Falls back to original text on error.
    """
    if not text.strip():
        return text
    # Same language → no need to translate
    tgt = target_lang.split("-")[0].lower()
    src = source_lang.lower() if source_lang != "auto" else "auto"
    if src != "auto" and src == tgt:
        return text
    try:
        from deep_translator import GoogleTranslator
        # deep-translator accepts 'zh-CN' as 'zh-CN' or 'chinese (simplified)'
        translated = GoogleTranslator(source=src, target=target_lang).translate(text)
        return translated or text
    except Exception as e:
        return f"[Translation error: {e}]"

# ─── Whisper Model (lazy-loaded, cached in session) ───────────────────────────
@st.cache_resource(show_spinner=False)
def load_whisper():
    """
    Load faster-whisper model once and reuse.
    Uses 'base' model for balance of speed/accuracy.
    'small' gives better multilingual results but is slower.
    Falls back gracefully if faster-whisper is unavailable.
    """
    try:
        from faster_whisper import WhisperModel
        # Try GPU first (compute_type="float16"), fall back to CPU (int8)
        try:
            model = WhisperModel("base", device="cuda", compute_type="float16")
            return model, "faster-whisper (GPU)"
        except Exception:
            model = WhisperModel("base", device="cpu", compute_type="int8")
            return model, "faster-whisper (CPU)"
    except ImportError:
        return None, "not_installed"

# ─── Audio Recording Thread ───────────────────────────────────────────────────
"""
HOW AUDIO CAPTURE WORKS:
  sounddevice opens the default microphone and fires a callback every ~200ms
  with a numpy array of float32 PCM samples. Each chunk goes into a thread-safe
  queue. The main recording loop drains the queue, appends chunks to a buffer,
  computes RMS energy, and detects silence (RMS < threshold for >3 seconds).
  When silence is detected the buffer is flushed to a WAV file → Whisper.
"""

SAMPLE_RATE   = 16000   # Hz — Whisper expects 16 kHz
CHUNK_SECONDS = 0.2     # seconds per callback chunk
CHUNK_FRAMES  = int(SAMPLE_RATE * CHUNK_SECONDS)
SILENCE_RMS   = 0.008   # RMS below this = silence (tune to your mic)
SILENCE_SECS  = 3.0     # seconds of silence before flush
MAX_SEGMENT   = 30.0    # max segment length in seconds (safety cap)

# Global audio queue (persists across Streamlit reruns via session state trick)
if "audio_queue" not in st.session_state:
    st.session_state.audio_queue = queue.Queue()
if "recording_active" not in st.session_state:
    st.session_state.recording_active = False
if "last_transcript" not in st.session_state:
    st.session_state.last_transcript = ""
if "last_lang" not in st.session_state:
    st.session_state.last_lang = ""
if "rec_status" not in st.session_state:
    st.session_state.rec_status = "idle"   # idle | listening | processing
if "level_rms" not in st.session_state:
    st.session_state.level_rms = 0.0

_stop_event = threading.Event()
_worker_thread = None

def _audio_callback(indata, frames, time_info, status):
    """sounddevice callback — called every CHUNK_FRAMES samples."""
    if st.session_state.get("recording_active"):
        st.session_state.audio_queue.put(indata.copy())

def _save_wav(audio_np: np.ndarray, path: str):
    """Write float32 numpy array as 16-bit PCM WAV."""
    pcm = (audio_np * 32767).astype(np.int16)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(pcm.tobytes())

def _transcribe_wav(path: str, model) -> tuple[str, str]:
    """
    Transcribe a WAV file using faster-whisper.
    Returns (transcript_text, detected_language_code).

    KEY SETTINGS:
      task="transcribe"  → keep original language (NOT translate to English)
      language=None      → auto-detect (supports 99 languages incl. Arabic dialects)
      beam_size=5        → balanced accuracy
      vad_filter=True    → skip silent segments (faster)
    """
    segments, info = model.transcribe(
        path,
        task="transcribe",   # ← transcribe in original language
        language=None,       # ← auto-detect language
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        word_timestamps=False,
    )
    text = " ".join(seg.text.strip() for seg in segments).strip()
    detected = info.language  # e.g. "ar", "fr", "en"
    return text, detected

def _recording_worker(stop_event: threading.Event):
    """
    Background thread:
      1. Opens microphone stream
      2. Drains audio_queue, builds buffer
      3. Computes RMS silence detection
      4. On silence or max length → transcribe → save to DB
    """
    try:
        import sounddevice as sd
    except ImportError:
        st.session_state.rec_status = "error_sounddevice"
        return

    model, backend = load_whisper()
    if model is None:
        st.session_state.rec_status = "error_whisper"
        return

    buffer = []
    silence_chunks = 0
    SILENCE_CHUNKS_NEEDED = int(SILENCE_SECS / CHUNK_SECONDS)
    max_chunks = int(MAX_SEGMENT / CHUNK_SECONDS)

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=CHUNK_FRAMES,
            callback=_audio_callback,
        ):
            st.session_state.rec_status = "listening"
            set_speaker_state("listening")

            while not stop_event.is_set():
                try:
                    chunk = st.session_state.audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                flat = chunk.flatten()
                rms = float(np.sqrt(np.mean(flat ** 2)))
                st.session_state.level_rms = rms
                buffer.append(flat)

                if rms < SILENCE_RMS:
                    silence_chunks += 1
                else:
                    silence_chunks = 0

                flush = (
                    silence_chunks >= SILENCE_CHUNKS_NEEDED
                    or len(buffer) >= max_chunks
                )

                if flush and buffer:
                    # Only process if there was actual speech
                    all_audio = np.concatenate(buffer)
                    buffer = []
                    silence_chunks = 0

                    rms_total = float(np.sqrt(np.mean(all_audio ** 2)))
                    if rms_total < SILENCE_RMS * 0.5:
                        # Pure silence — skip
                        continue

                    st.session_state.rec_status = "processing"
                    set_speaker_state("processing")

                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                        tmp_path = tmp.name
                    try:
                        _save_wav(all_audio, tmp_path)
                        text, lang = _transcribe_wav(tmp_path, model)
                        if text:
                            save_segment(text, lang)
                            st.session_state.last_transcript = text
                            st.session_state.last_lang = lang
                    except Exception as e:
                        pass  # silently skip bad segments
                    finally:
                        os.unlink(tmp_path)

                    st.session_state.rec_status = "listening"
                    set_speaker_state("listen
