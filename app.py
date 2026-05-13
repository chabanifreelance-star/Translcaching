import streamlit as st
import sqlite3, os, tempfile, random, string, html, re, time, json
from datetime import datetime

st.set_page_config(
    page_title="LiveTranslate",
    page_icon="🇵🇸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

def esc(text: str) -> str:
    return html.escape(str(text), quote=True)

RTL_LANGS = {"ar", "he", "fa", "ur", "yi", "ps", "ku", "dv", "ug", "ckb"}

def dir_attr(lang_code: str) -> str:
    base = (lang_code or "").split("-")[0].lower()
    return "rtl" if base in RTL_LANGS else "ltr"

def rtl_style(lang_code: str) -> str:
    if dir_attr(lang_code) == "rtl":
        return "direction:rtl;text-align:right;unicode-bidi:embed;"
    return "direction:ltr;text-align:left;"

def sanitize_code(raw: str) -> str:
    return re.sub(r"[^0-9]", "", (raw or ""))[:4]

UI_STRINGS = {
    "en": {
        "hero_line1": "LIVE",
        "hero_line2": "TRANSLATE",
        "app_sub": "Real-time multilingual subtitles",
        "speaker_btn": "🎤  SPEAKER",
        "audience_btn": "👥  AUDIENCE",
        "footer": "faster-whisper · deep-translator · 100% free",
        "your_room": "YOUR ROOM",
        "share_code": "Share this code with your audience",
        "room_code_lbl": "🔑 Room Code",
        "code_hint": "Tell your audience to enter this code",
        "enter_speak": "🎤  Enter Room & Speak",
        "new_code": "🔄  New Code",
        "back_home": "← Back to Home",
        "join_room": "JOIN ROOM",
        "enter_code": "Enter the 4-digit code from the speaker",
        "join_btn": "👥  Join Room",
        "back": "← Back",
        "ask_speaker": "Ask the <b>Speaker</b> for the 4-digit room code.<br>Each room is private — only that room's subtitles appear.",
        "speak_now": "SPEAK NOW",
        "tap_mic": "Tap mic · speak · tap again",
        "speaking_lang": "Speaking language",
        "tap_hint": "🎙️  tap mic · speak · tap again to transcribe",
        "home_btn": "← Home",
        "clear_btn": "🗑 Clear",
        "nothing_yet": "Nothing yet — tap the mic above",
        "live_subs": "LIVE SUBS",
        "realtime_subs": "Real-time translated subtitles",
        "language": "Language",
        "refresh": "Refresh",
        "waiting": "Waiting for speaker…",
        "will_broadcast": "The speaker will broadcast to this room",
        "speak_aloud": "🔊 Aloud",
        "copy_btn": "📋 Copy",
        "full_btn": "⛶ Full",
        "tap_close": "Tap to close",
        "previous": "─── PREVIOUS ───",
        "font": "font",
        "segs": "segs",
        "room": "Room",
        "live_dot": "🔴 Live",
    },
    "fr": {
        "hero_line1": "LIVE",
        "hero_line2": "TRADUCTION",
        "app_sub": "Multilingues en temps réel",
        "speaker_btn": "🎤  ORATEUR",
        "audience_btn": "👥  AUDIENCE",
        "footer": "faster-whisper · deep-translator · 100% gratuit",
        "your_room": "VOTRE SALLE",
        "share_code": "Partagez ce code avec votre audience",
        "room_code_lbl": "🔑 Code de salle",
        "code_hint": "Dites à votre audience d'entrer ce code",
        "enter_speak": "🎤  Entrer & Parler",
        "new_code": "🔄  Nouveau Code",
        "back_home": "← Retour à l'accueil",
        "join_room": "REJOINDRE",
        "enter_code": "Entrez le code 4 chiffres du conférencier",
        "join_btn": "👥  Rejoindre",
        "back": "← Retour",
        "ask_speaker": "Demandez le code 4 chiffres au <b>Conférencier</b>.<br>Chaque salle est privée — seuls ses sous-titres apparaissent.",
        "speak_now": "PARLEZ MAINTENANT",
        "tap_mic": "Appuyez · parlez · appuyez encore",
        "speaking_lang": "Langue de discours",
        "tap_hint": "🎙️  appuyez · parlez · appuyez encore pour transcrire",
        "home_btn": "← Accueil",
        "clear_btn": "🗑 Effacer",
        "nothing_yet": "Rien encore — appuyez sur le micro",
        "live_subs": "SOUS-TITRES",
        "realtime_subs": "Sous-titres traduits en temps réel",
        "language": "Langue",
        "refresh": "Rafraîchir",
        "waiting": "En attente du conférencier…",
        "will_broadcast": "Le conférencier diffusera dans cette salle",
        "speak_aloud": "🔊 À voix haute",
        "copy_btn": "📋 Copier",
        "full_btn": "⛶ Plein",
        "tap_close": "Appuyer pour fermer",
        "previous": "─── PRÉCÉDENT ───",
        "font": "police",
        "segs": "segs",
        "room": "Salle",
        "live_dot": "🔴 En direct",
    },
    "ar": {
        "hero_line1": "مباشر",
        "hero_line2": "ترجمة",
        "app_sub": "ترجمة فورية متعددة اللغات",
        "speaker_btn": "🎤  المتحدث",
        "audience_btn": "👥  الجمهور",
        "footer": "faster-whisper · deep-translator · مجاني 100%",
        "your_room": "غرفتك",
        "share_code": "شارك هذا الرمز مع جمهورك",
        "room_code_lbl": "🔑 رمز الغرفة",
        "code_hint": "أخبر جمهورك بإدخال هذا الرمز",
        "enter_speak": "🎤  ادخل الغرفة وتحدث",
        "new_code": "🔄  رمز جديد",
        "back_home": "→ العودة للرئيسية",
        "join_room": "انضم للغرفة",
        "enter_code": "أدخل الرمز المكون من 4 أرقام من المتحدث",
        "join_btn": "👥  انضم",
        "back": "→ رجوع",
        "ask_speaker": "اطلب من <b>المتحدث</b> رمز الغرفة المكون من 4 أرقام.<br>كل غرفة خاصة — تظهر ترجمتها فقط.",
        "speak_now": "تحدث الآن",
        "tap_mic": "اضغط الميكروفون · تحدث · اضغط مرة أخرى",
        "speaking_lang": "لغة الحديث",
        "tap_hint": "🎙️  اضغط · تحدث · اضغط مجدداً للنسخ",
        "home_btn": "→ الرئيسية",
        "clear_btn": "🗑 مسح",
        "nothing_yet": "لا شيء بعد — اضغط الميكروفون أعلاه",
        "live_subs": "ترجمة مباشرة",
        "realtime_subs": "ترجمة فورية في الوقت الحقيقي",
        "language": "اللغة",
        "refresh": "تحديث",
        "waiting": "في انتظار المتحدث…",
        "will_broadcast": "سيبث المتحدث في هذه الغرفة",
        "speak_aloud": "🔊 تشغيل",
        "copy_btn": "📋 نسخ",
        "full_btn": "⛶ ملء الشاشة",
        "tap_close": "اضغط للإغلاق",
        "previous": "─── السابق ───",
        "font": "خط",
        "segs": "مقطع",
        "room": "غرفة",
        "live_dot": "🔴 مباشر",
    },
    "tr": {
        "hero_line1": "CANLI",
        "hero_line2": "ÇEVİRİ",
        "app_sub": "Gerçek zamanlı çok dilli altyazılar",
        "speaker_btn": "🎤  KONUŞMACI",
        "audience_btn": "👥  KATİLİMCILAR",
        "footer": "faster-whisper · deep-translator · 100% ücretsiz",
        "your_room": "ODANIZ",
        "share_code": "Bu kodu izleyicilerinizle paylaşın",
        "room_code_lbl": "🔑 Oda Kodu",
        "code_hint": "İzleyicilerinize bu kodu girin deyin",
        "enter_speak": "🎤  Odaya Gir & Konuş",
        "new_code": "🔄  Yeni Kod",
        "back_home": "← Ana Sayfaya Dön",
        "join_room": "ODAYA KATIL",
        "enter_code": "Konuşmacının 4 haneli kodunu girin",
        "join_btn": "👥  Katıl",
        "back": "← Geri",
        "ask_speaker": "<b>Konuşmacıdan</b> 4 haneli oda kodunu isteyin.<br>Her oda özeldir — yalnızca o odanın altyazıları görünür.",
        "speak_now": "KONUŞUN",
        "tap_mic": "Mikrofona bas · konuş · tekrar bas",
        "speaking_lang": "Konuşma dili",
        "tap_hint": "🎙️  bas · konuş · transkript için tekrar bas",
        "home_btn": "← Ana Sayfa",
        "clear_btn": "🗑 Temizle",
        "nothing_yet": "Henüz bir şey yok — yukarıdaki mikrofona basın",
        "live_subs": "CANLI ALTYAZI",
        "realtime_subs": "Gerçek zamanlı çevrilmiş altyazılar",
        "language": "Dil",
        "refresh": "Yenile",
        "waiting": "Konuşmacı bekleniyor…",
        "will_broadcast": "Konuşmacı bu odaya yayın yapacak",
        "speak_aloud": "🔊 Sesli",
        "copy_btn": "📋 Kopyala",
        "full_btn": "⛶ Tam Ekran",
        "tap_close": "Kapatmak için dokun",
        "previous": "─── ÖNCEKİ ───",
        "font": "yazı tipi",
        "segs": "bölüm",
        "room": "Oda",
        "live_dot": "🔴 Canlı",
    },
    "es": {
        "hero_line1": "EN VIVO",
        "hero_line2": "TRADUCIR",
        "app_sub": "Subtítulos multilingües en tiempo real",
        "speaker_btn": "🎤  ORADOR",
        "audience_btn": "👥  AUDIENCIA",
        "footer": "faster-whisper · deep-translator · 100% gratis",
        "your_room": "TU SALA",
        "share_code": "Comparte este código con tu audiencia",
        "room_code_lbl": "🔑 Código de sala",
        "code_hint": "Dile a tu audiencia que ingrese este código",
        "enter_speak": "🎤  Entrar & Hablar",
        "new_code": "🔄  Nuevo Código",
        "back_home": "← Volver al inicio",
        "join_room": "UNIRSE A SALA",
        "enter_code": "Ingresa el código de 4 dígitos del orador",
        "join_btn": "👥  Unirse",
        "back": "← Atrás",
        "ask_speaker": "Pide al <b>Orador</b> el código de sala de 4 dígitos.<br>Cada sala es privada — solo aparecen sus subtítulos.",
        "speak_now": "HABLA AHORA",
        "tap_mic": "Toca el micrófono · habla · toca de nuevo",
        "speaking_lang": "Idioma de habla",
        "tap_hint": "🎙️  toca · habla · toca de nuevo para transcribir",
        "home_btn": "← Inicio",
        "clear_btn": "🗑 Limpiar",
        "nothing_yet": "Nada todavía — toca el micrófono arriba",
        "live_subs": "SUBTÍTULOS",
        "realtime_subs": "Subtítulos traducidos en tiempo real",
        "language": "Idioma",
        "refresh": "Refrescar",
        "waiting": "Esperando al orador…",
        "will_broadcast": "El orador transmitirá a esta sala",
        "speak_aloud": "🔊 En voz alta",
        "copy_btn": "📋 Copiar",
        "full_btn": "⛶ Pantalla completa",
        "tap_close": "Toca para cerrar",
        "previous": "─── ANTERIORES ───",
        "font": "fuente",
        "segs": "segs",
        "room": "Sala",
        "live_dot": "🔴 En vivo",
    },
}

def T(key: str) -> str:
    lang = st.session_state.get("ui_lang", "en")
    return UI_STRINGS.get(lang, UI_STRINGS["en"]).get(key, UI_STRINGS["en"].get(key, key))

def is_rtl_ui() -> bool:
    return st.session_state.get("ui_lang", "en") == "ar"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=Noto+Naskh+Arabic:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

#MainMenu,header,footer,
[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stStatusWidget"]{display:none!important;}

.stApp{background:#050505!important;}
.block-container{padding:0!important;max-width:100%!important;}
body,html{overflow-x:hidden!important;}

.stButton>button{
  background:linear-gradient(135deg,#0a0a0a,#111)!important;
  border:1px solid #222!important;
  color:#f2ede3!important;
  border-radius:14px!important;
  font-weight:700!important;
  font-size:13px!important;
  padding:12px 8px!important;
  width:100%!important;
  font-family:'Cairo',sans-serif!important;
  letter-spacing:.04em!important;
  transition:all .2s cubic-bezier(.4,0,.2,1)!important;
}
.stButton>button:hover{
  background:linear-gradient(135deg,#111,#181818)!important;
  border-color:#007a3d!important;
  transform:translateY(-1px)!important;
  box-shadow:0 4px 20px rgba(0,122,61,.18)!important;
}
.stButton>button:active{transform:translateY(0)!important;}

.stTextInput>div>div>input{
  background:#080808!important;
  border:1px solid #222!important;
  color:#f2ede3!important;
  border-radius:14px!important;
  font-size:24px!important;
  text-align:center!important;
  letter-spacing:10px!important;
  font-weight:700!important;
  font-family:'JetBrains Mono',monospace!important;
  padding:16px!important;
  transition:border-color .2s!important;
}
.stTextInput>div>div>input:focus{
  border-color:#007a3d!important;
  box-shadow:0 0 0 2px rgba(0,122,61,.12)!important;
}
.stTextInput label{
  color:#444!important;font-size:10px!important;
  letter-spacing:.18em!important;text-transform:uppercase!important;
  font-family:'JetBrains Mono',monospace!important;
}
.stSelectbox>div>div{
  background:#080808!important;border:1px solid #222!important;
  border-radius:12px!important;color:#f2ede3!important;
}
iframe{display:block!important;}
div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;}
.pal-divider{
  height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%,#007a3d 100%);
  border-radius:3px;margin:6px 0;
}
</style>
""", unsafe_allow_html=True)

PALETTE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=Noto+Naskh+Arabic:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
:root{
  --bg:#050505;--card:#080808;--b:#1a1a1a;--b2:#252525;
  --white:#f2ede3;--dim:#222;
  --green:#007a3d;--gl:#00c65e;
  --red:#ce1126;--rl:#ff3348;
  --black:#000;
  --melon:#fd6b4b;--ml:#ff8a6a;
}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{
  background:transparent;color:var(--white);
  font-family:'Cairo','Noto Naskh Arabic',sans-serif;
  -webkit-font-smoothing:antialiased;overflow-x:hidden;
}
.rtl-text{
  direction:rtl;text-align:right;unicode-bidi:embed;
  font-family:'Noto Naskh Arabic','Cairo',sans-serif;
  font-feature-settings:"kern" 1,"liga" 1,"calt" 1;
}
.ltr-text{direction:ltr;text-align:left;unicode-bidi:embed;font-family:'Cairo',sans-serif;}
</style>
"""

DB = os.path.join(tempfile.gettempdir(), "lt_pal_v2.db")

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    with _cx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS rooms(code TEXT PRIMARY KEY, created TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS seg(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL, txt TEXT NOT NULL,
            lang TEXT DEFAULT '', ts TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS rate_limit(
            room TEXT PRIMARY KEY, last_save REAL NOT NULL, count INTEGER DEFAULT 0)""")
        c.commit()

def room_create(code):
    with _cx() as c:
        c.execute("INSERT OR IGNORE INTO rooms(code,created) VALUES(?,?)",
                  (code, datetime.now().strftime("%H:%M")))
        c.commit()

def room_exists(code):
    if not re.fullmatch(r"[0-9]{4}", code or ""):
        return False
    with _cx() as c:
        return c.execute("SELECT 1 FROM rooms WHERE code=?", (code,)).fetchone() is not None

def _check_rate_limit(room: str, max_per_minute: int = 30) -> bool:
    now = time.time()
    with _cx() as c:
        row = c.execute("SELECT last_save, count FROM rate_limit WHERE room=?", (room,)).fetchone()
        if row is None:
            c.execute("INSERT INTO rate_limit(room,last_save,count) VALUES(?,?,1)", (room, now))
            c.commit()
            return True
        last_save, count = row
        if now - last_save > 60:
            c.execute("UPDATE rate_limit SET last_save=?, count=1 WHERE room=?", (now, room))
            c.commit()
            return True
        if count >= max_per_minute:
            return False
        c.execute("UPDATE rate_limit SET count=count+1 WHERE room=?", (room,))
        c.commit()
        return True

def db_save(room, txt, lang):
    try:
        if not _check_rate_limit(room):
            return False
        clean = txt.strip()[:2000]
        if not clean:
            return False
        with _cx() as c:
            c.execute("INSERT INTO seg(room,txt,lang,ts) VALUES(?,?,?,?)",
                      (room, clean, lang, datetime.now().strftime("%H:%M")))
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
                (room, limit)).fetchall()
    except Exception:
        return []

def db_count(room):
    try:
        if not re.fullmatch(r"[0-9]{4}", room or ""):
            return 0
        with _cx() as c:
            return c.execute("SELECT COUNT(*) FROM seg WHERE room=?", (room,)).fetchone()[0]
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

@st.cache_resource(show_spinner=False)
def get_whisper_base():
    """Small model for non-Arabic languages."""
    try:
        from faster_whisper import WhisperModel
        try:
            return WhisperModel("small", device="cuda", compute_type="float16")
        except Exception:
            return WhisperModel("small", device="cpu", compute_type="int8")
    except Exception:
        return None

@st.cache_resource(show_spinner=False)
def get_whisper_arabic():
    """Large-v2 for Arabic — base/small hallucinate heavily on Arabic."""
    try:
        from faster_whisper import WhisperModel
        try:
            return WhisperModel("large-v2", device="cuda", compute_type="float16")
        except Exception:
            return WhisperModel("large-v2", device="cpu", compute_type="int8")
    except Exception:
        try:
            from faster_whisper import WhisperModel
            return WhisperModel("medium", device="cpu", compute_type="int8")
        except Exception:
            return None

_AR_HALLUCINATIONS = {
    "شكراً", "شكرا", "شكراً للمشاهدة", "شكرا للمشاهدة",
    "للمشاهدة", "للاستماع", "مع السلامة", "إلى اللقاء",
    "أراكم في الحلقة القادمة", "تابعونا", "اشتركوا في القناة",
    "سبحان الله", "بسم الله الرحمن الرحيم", ".", "..", "...", " ", "",
}

def _is_hallucination(text: str, lang_code: str) -> bool:
    t = text.strip()
    if not t or len(t) < 2:
        return True
    if lang_code == "ar":
        if t in _AR_HALLUCINATIONS:
            return True
        ar_chars = sum(1 for c in t if '\u0600' <= c <= '\u06FF')
        if len(t) > 0 and ar_chars == 0:
            return True
    return False

def transcribe(audio_bytes: bytes, lang_code: str):
    is_arabic = lang_code == "ar"
    model = get_whisper_arabic() if is_arabic else get_whisper_base()
    if not model:
        model = get_whisper_base()
    if not model:
        return "", lang_code
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes); tmp = f.name
        if is_arabic:
            segs, _ = model.transcribe(
                tmp, task="transcribe", language="ar",
                beam_size=5, best_of=5,
                temperature=[0.0, 0.2, 0.4],
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.0,
                log_prob_threshold=-0.8,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 300, "speech_pad_ms": 200, "threshold": 0.45},
                initial_prompt="هذا نص باللغة العربية الفصحى.",
            )
            parts = []
            for s in segs:
                txt = s.text.strip()
                if _is_hallucination(txt, "ar"):
                    continue
                if hasattr(s, 'avg_logprob') and s.avg_logprob < -1.0:
                    continue
                if hasattr(s, 'compression_ratio') and s.compression_ratio > 2.4:
                    continue
                parts.append(txt)
            return " ".join(parts).strip(), lang_code
        else:
            segs, _ = model.transcribe(
                tmp, task="transcribe", language=lang_code,
                beam_size=5, vad_filter=True,
                condition_on_previous_text=False,
                vad_parameters={"min_silence_duration_ms": 400},
            )
            return " ".join(s.text.strip() for s in segs).strip(), lang_code
    except Exception:
        return "", lang_code
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass


_LANG_MAP = {"zh-cn": "zh-CN", "zh-tw": "zh-TW", "ar": "ar", "he": "iw"}

def _norm_for_google(code: str) -> str:
    c = (code or "").strip()
    low = c.lower()
    if low in _LANG_MAP:
        return _LANG_MAP[low]
    if low.startswith("zh"):
        return c
    return low.split("-")[0]

_TR_CACHE: dict = {}
_TR_CACHE_MAX = 2000

def tr(text: str, target: str, source: str) -> str:
    """Translate. Uses source=auto for Arabic to handle all dialects correctly."""
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
        # Arabic dialects (Egyptian, Gulf, Levantine…) translate better with auto-detect
        use_src = "auto" if src in ("ar", "iw", "fa", "ur") else src
        result = GoogleTranslator(source=use_src, target=tgt).translate(text)
        if not result or not result.strip():
            result = GoogleTranslator(source=src, target=tgt).translate(text)
        translated = result if result and result.strip() else text
    except Exception:
        translated = text
    if len(_TR_CACHE) >= _TR_CACHE_MAX:
        oldest = next(iter(_TR_CACHE))
        del _TR_CACHE[oldest]
    _TR_CACHE[cache_key] = translated
    return translated

SPEAKER_LANGS = {
    "🇬🇧 English": "en",
    "🇸🇦 Arabic":  "ar",
    "🇫🇷 French":  "fr",
    "🇹🇷 Turkish": "tr",
    "🇪🇸 Spanish": "es",
    "🇩🇪 German":  "de",
    "🇮🇹 Italian": "it",
    "🇷🇺 Russian": "ru",
}

AUDIENCE_LANGS = {
    "🇸🇦 Arabic":     "ar",  "🇬🇧 English":   "en",
    "🇫🇷 French":     "fr",  "🇪🇸 Spanish":   "es",
    "🇩🇪 German":     "de",  "🇹🇷 Turkish":   "tr",
    "🇮🇹 Italian":    "it",  "🇨🇳 Chinese":   "zh-CN",
    "🇷🇺 Russian":    "ru",  "🇯🇵 Japanese":  "ja",
    "🇧🇷 Portuguese": "pt",  "🇮🇳 Hindi":     "hi",
    "🇰🇷 Korean":     "ko",  "🇳🇱 Dutch":     "nl",
    "🇵🇱 Polish":     "pl",  "🇸🇪 Swedish":   "sv",
    "🇬🇷 Greek":      "el",  "🇹🇭 Thai":      "th",
    "🇻🇳 Vietnamese": "vi",  "🇺🇦 Ukrainian": "uk",
    "🇮🇩 Indonesian": "id",
}

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
    "ui_lang":    "en",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(page, **kw):
    st.session_state.page = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()

UI_LANG_OPTIONS = [
    ("🇬🇧 EN", "en"),
    ("🇫🇷 FR", "fr"),
    ("🇸🇦 AR", "ar"),
    ("🇹🇷 TR", "tr"),
    ("🇪🇸 ES", "es"),
]

def render_lang_toggle():
    """Single toggle button that cycles through UI languages. Home page only."""
    codes = [code for _, code in UI_LANG_OPTIONS]
    labels = [label for label, _ in UI_LANG_OPTIONS]
    cur = st.session_state.ui_lang
    cur_idx = codes.index(cur) if cur in codes else 0
    cur_label = labels[cur_idx]
    next_idx = (cur_idx + 1) % len(codes)
    next_label = labels[next_idx]

    st.markdown("""<div style='height:6px'></div>""", unsafe_allow_html=True)
    st.markdown(f"""<style>
div[data-testid="stButton"][key="lang_toggle"] .stButton>button,
.lang-toggle-btn .stButton>button{{
  border-color:#007a3d!important;
  background:rgba(0,122,61,.13)!important;
  color:#00c65e!important;
  font-size:12px!important;
  letter-spacing:.12em!important;
}}
</style>""", unsafe_allow_html=True)

    col_l, col_btn, col_r = st.columns([3, 2, 3])
    with col_btn:
        if st.button(f"{cur_label}  →  {next_label}", key="lang_toggle", use_container_width=True):
            st.session_state.ui_lang = codes[next_idx]
            st.rerun()
    st.markdown("""<div class='pal-divider'></div>""", unsafe_allow_html=True)


if st.session_state.page == "home":

    render_lang_toggle()

    rtl = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"
    ui_align = "right" if rtl else "center"

    st.iframe(PALETTE + f"""
<style>
body{{
  display:flex;flex-direction:column;align-items:center;
  padding:16px 16px 12px;text-align:{ui_align};background:transparent;
  direction:{ui_dir};
}}
.kufic{{
  font-family:{'\'Noto Naskh Arabic\',\'Cairo\'' if rtl else '\'Bebas Neue\''};
  font-size:clamp({'44px,11vw,80px' if rtl else '60px,15vw,108px'});
  line-height:.85;letter-spacing:{'.02em' if rtl else '.03em'};
  font-weight:{'900' if rtl else 'normal'};
}}
.live-word{{
  background:linear-gradient(135deg,#ff3348 0%,#fd6b4b 45%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.tr-word{{
  background:linear-gradient(135deg,#fd6b4b 0%,#ff8a6a 55%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:11px;color:#666;letter-spacing:.14em;text-transform:uppercase;
  margin-top:12px;font-family:{'\'Noto Naskh Arabic\',\'Cairo\'' if rtl else '\'JetBrains Mono\',monospace'};}}
.pal-bar{{
  display:flex;width:86%;max-width:310px;height:4px;border-radius:4px;
  overflow:hidden;margin:14px auto 0;
}}
.pb-r{{flex:1;background:#fd6b4b;}}
.pb-m{{flex:1;background:#ff8a6a;}}
.pb-d{{flex:1;background:#e85530;}}
.pb-w{{flex:1;background:#ce1126;}}
@keyframes pulse{{0%,100%{{box-shadow:0 0 0 0 rgba(253,107,75,0)}}50%{{box-shadow:0 0 20px 5px rgba(253,107,75,.14)}}}}
.pal-bar{{animation:pulse 3.5s infinite;}}
</style>
<div class="kufic">
  <span class="live-word">{esc(T("hero_line1"))}</span><br>
  <span class="tr-word">{esc(T("hero_line2"))}</span>
</div>
<div class="sub">{esc(T("app_sub"))} 🇵🇸</div>
<div class="pal-bar">
  <div class="pb-r"></div><div class="pb-m"></div>
  <div class="pb-d"></div><div class="pb-w"></div>
</div>
""", height=220)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button(T("speaker_btn"), key="btn_spk", use_container_width=True):
            go("speaker_setup")
    with col2:
        if st.button(T("audience_btn"), key="btn_aud", use_container_width=True):
            go("audience_join")

    st.markdown(f"""
<div style='text-align:center;font-size:9px;color:#1c1c1c;
  letter-spacing:.07em;padding:10px 0 4px;font-family:monospace;'>
  {esc(T("footer"))} 🇵🇸
</div>""", unsafe_allow_html=True)


elif st.session_state.page == "speaker_setup":

    if not st.session_state.room_code:
        code = gen_code()
        room_create(code)
        st.session_state.room_code = code

    code = st.session_state.room_code
    rtl = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    st.iframe(PALETTE + f"""
<style>
body{{padding:16px 16px 6px;background:transparent;direction:{ui_dir};}}
.title{{
  font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;
  margin-top:7px;font-family:'Cairo',sans-serif;}}
</style>
<div class="title">{esc(T("your_room"))}</div>
<div class="sub">{esc(T("share_code"))}</div>
""", height=86)

    st.iframe(PALETTE + f"""
<style>
body{{
  display:flex;flex-direction:column;align-items:center;
  padding:6px 16px 10px;text-align:center;background:transparent;
}}
.lbl{{font-size:10px;color:#333;letter-spacing:.18em;text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;margin-bottom:10px;}}
.outer{{
  padding:2px;border-radius:24px;
  background:linear-gradient(135deg,#ce1126,#000 40%,#007a3d);
}}
.box{{
  background:#060606;border-radius:22px;padding:22px 40px 16px;
}}
.code{{
  font-family:'Bebas Neue',sans-serif;
  font-size:clamp(88px,24vw,136px);
  letter-spacing:18px;line-height:1;
  background:linear-gradient(135deg,#ff3348,#ff8a6a,#fff);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.hint{{font-size:11px;color:#2a2a2a;margin-top:7px;font-family:'JetBrains Mono',monospace;}}
</style>
<div class="lbl">{esc(T("room_code_lbl"))}</div>
<div class="outer">
  <div class="box">
    <div class="code">{esc(code)}</div>
    <div class="hint">{esc(T("code_hint"))}</div>
  </div>
</div>
""", height=212)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button(T("enter_speak"), key="spk_enter", use_container_width=True):
            go("speaker")
    with c2:
        if st.button(T("new_code"), key="spk_newcode", use_container_width=True):
            c = gen_code()
            room_create(c)
            st.session_state.room_code = c
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button(T("back_home"), key="spk_setup_back", use_container_width=True):
        go("home", room_code=None)


elif st.session_state.page == "audience_join":

    rtl = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    st.iframe(PALETTE + f"""
<style>
body{{padding:16px 16px 6px;background:transparent;direction:{ui_dir};}}
.title{{
  font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;
  margin-top:7px;font-family:'Cairo',sans-serif;}}
</style>
<div class="title">{esc(T("join_room"))}</div>
<div class="sub">{esc(T("enter_code"))}</div>
""", height=86)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    code_input = st.text_input("ROOM CODE", max_chars=4, placeholder="1234", key="aud_code_field")

    if st.session_state.join_error:
        st.markdown(f"""
<div style='background:rgba(206,17,38,.1);border:1px solid rgba(255,51,72,.28);
  border-radius:12px;padding:12px 14px;font-size:13px;color:#ff3348;
  text-align:center;margin:6px 0;font-family:"Cairo",sans-serif;'>
  ❌ {esc(st.session_state.join_error)}
</div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    j1, j2 = st.columns(2, gap="small")
    with j1:
        if st.button(T("join_btn"), key="aud_join_btn", use_container_width=True):
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
        if st.button(T("back"), key="aud_join_back", use_container_width=True):
            st.session_state.join_error = ""
            go("home")

    ask_dir = "rtl" if rtl else "ltr"
    st.iframe(PALETTE + f"""
<style>
body{{padding:12px 0;background:transparent;direction:{ask_dir};}}
.tip{{
  background:#060606;border-radius:16px;padding:18px 16px;text-align:center;
  position:relative;overflow:hidden;
}}
.tip::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);
}}
.icon{{font-size:28px;margin-bottom:8px;}}
.t{{font-size:12px;color:#2e2e2e;line-height:1.7;font-family:'Cairo',sans-serif;}}
.t b{{color:#3a3a3a;}}
</style>
<div class="tip">
  <div class="icon">💡</div>
  <div class="t">{T("ask_speaker")}</div>
</div>
""", height=128)


elif st.session_state.page == "speaker":

    if not st.session_state.room_code:
        go("speaker_setup")

    room = st.session_state.room_code
    rtl = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    nl, nr = st.columns([3, 1], gap="small")
    with nl:
        st.iframe(PALETTE + f"""
<style>
body{{padding:16px 16px 4px;background:transparent;direction:{ui_dir};}}
.title{{
  font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;margin-top:6px;font-family:'Cairo',sans-serif;}}
.badge{{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(253,107,75,.1);border:1px solid rgba(253,107,75,.25);
  border-radius:8px;padding:4px 10px;margin-top:7px;
  font-size:11px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">{esc(T("speak_now"))}</div>
<div class="sub">{esc(T("tap_mic"))}</div>
<div class="badge">🔑 {esc(T("room"))} {esc(room)}</div>
""", height=112)
    with nr:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(T("home_btn"), key="spk_home", use_container_width=True):
            go("home", room_code=None)

    spk_label = st.selectbox(
        T("speaking_lang"),
        list(SPEAKER_LANGS.keys()),
        index=list(SPEAKER_LANGS.values()).index(st.session_state.spk_lang),
        key="spk_lang_sel",
    )
    st.session_state.spk_lang = SPEAKER_LANGS[spk_label]

    st.markdown(f"""
<div style='font-size:11px;color:#2a2a2a;letter-spacing:.1em;text-transform:uppercase;
  font-family:monospace;text-align:center;padding:6px 0 2px;'>
  {esc(T("tap_hint"))}
</div>""", unsafe_allow_html=True)

    rec = st.audio_input("mic", key="mic_input", label_visibility="collapsed")

    if rec:
        audio_bytes = rec.read()
        h = hash(audio_bytes)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            lang_code = st.session_state.spk_lang
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
        st.iframe(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
body{{margin:0;padding:3px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:8px;padding:10px 14px;
  background:#060606;border:1px solid #161616;border-radius:10px;
  font-size:12px;font-family:monospace;'>
  <span style='width:8px;height:8px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.18);
    animation:dp 1.4s infinite;flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    <b>{n}</b> {esc(T("segs"))} · <b>{esc(st.session_state.spk_lang.upper())}</b> · {esc(T("room"))} <b>{esc(room)}</b>
  </span>
</div>""", height=46)
    with s2:
        if st.button(T("clear_btn"), key="clr_btn", use_container_width=True):
            db_clear(room)
            st.session_state.last_txt = ""
            st.rerun()

    rows = db_all(room, 60)
    if not rows:
        st.iframe(PALETTE + f"""
<style>body{{padding:28px 0;text-align:center;background:transparent;}}</style>
<div style='font-size:38px;margin-bottom:8px;'>🎙️</div>
<div style='font-size:13px;color:#2a2a2a;font-family:"Cairo",sans-serif;'>{esc(T("nothing_yet"))}</div>
""", height=90)
    else:
        cards = ""
        for i, (txt, lang, ts) in enumerate(rows):
            safe_txt  = esc(txt)
            safe_lang = esc((lang or "??").upper())
            safe_ts   = esc(ts)
            d   = dir_attr(lang)
            rs  = rtl_style(lang)
            new = i == 0
            bl  = "border-left:3px solid #fd6b4b;" if new else ""
            bg  = "background:linear-gradient(135deg,rgba(253,107,75,.06),#080808 55%);" if new else ""
            an  = "animation:sl .35s ease;" if new else ""
            nt  = '<span class="ntag">NEW</span>' if new else ""
            cards += f"""
<div class="hc" style="{bl}{bg}{an}">
  <div class="meta">
    <span class="ts">🕐 {safe_ts}</span>
    <span class="ltag">{safe_lang}</span>{nt}
  </div>
  <div class="htxt" dir="{d}" style="{rs}">{safe_txt}</div>
</div>"""
        st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 24px;}}
@keyframes sl{{from{{opacity:.1;transform:translateY(-6px)}}to{{opacity:1;transform:none}}}}
.hc{{background:#070707;border:1px solid #161616;border-radius:14px;
  padding:14px 16px;margin:5px 0;transition:border-color .2s;}}
.hc:hover{{border-color:#252525;}}
.meta{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:7px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#2a2a2a;}}
.ltag{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);
  border-radius:5px;padding:1px 8px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ntag{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);
  border-radius:5px;padding:1px 8px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.htxt{{font-size:16px;font-weight:600;color:#f2ede3;line-height:1.65;
  font-family:'Noto Naskh Arabic','Cairo',sans-serif;}}
</style>
{cards}
""", height=min(80 + len(rows) * 90, 2400))


elif st.session_state.page == "audience":

    if not st.session_state.room_code:
        go("audience_join")

    room = st.session_state.room_code
    rtl = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    al, ar_ = st.columns([3, 1], gap="small")
    with al:
        st.iframe(PALETTE + f"""
<style>
body{{padding:16px 16px 4px;background:transparent;direction:{ui_dir};}}
.title{{
  font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);
  line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;
}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;
  margin-top:6px;font-family:'Cairo',sans-serif;}}
.badge{{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(0,122,61,.1);border:1px solid rgba(0,198,94,.25);
  border-radius:8px;padding:4px 10px;margin-top:7px;
  font-size:11px;color:#00c65e;font-family:'JetBrains Mono',monospace;font-weight:700;
}}
</style>
<div class="title">{esc(T("live_subs"))}</div>
<div class="sub">{esc(T("realtime_subs"))}</div>
<div class="badge">🔑 {esc(T("room"))} {esc(room)}</div>
""", height=112)
    with ar_:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(T("home_btn"), key="aud_home", use_container_width=True):
            go("home", room_code=None)

    c1, c2 = st.columns([3, 1], gap="small")
    with c1:
        lc_sel = st.selectbox(
            T("language"),
            list(AUDIENCE_LANGS.keys()),
            index=list(AUDIENCE_LANGS.values()).index(st.session_state.aud_lang),
            label_visibility="collapsed",
            key="aud_lang_sel",
        )
        st.session_state.aud_lang = AUDIENCE_LANGS[lc_sel]
    with c2:
        rate = st.selectbox(
            T("refresh"),
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
<div style='text-align:center;font-size:12px;color:#3a3a3a;
  font-family:monospace;padding:9px 0;'>
  {esc(T("font"))} <b style='color:#555;'>{fpx}px</b>
</div>""", unsafe_allow_html=True)
    with f3:
        if st.button("A+", key="fup", use_container_width=True):
            st.session_state.aud_fpx = min(64, st.session_state.aud_fpx + 4)

    st.iframe("""<script>
(async()=>{
  if('wakeLock' in navigator){
    try{await navigator.wakeLock.request('screen');}catch(e){}
    document.addEventListener('visibilitychange',async()=>{
      if(document.visibilityState==='visible')
        try{await navigator.wakeLock.request('screen');}catch(e){}
    });
  }
})();
</script>""", height=1)

    @st.fragment(run_every=st.session_state.aud_rate)
    def live_display():
        tgt       = st.session_state.aud_lang
        fpx       = st.session_state.aud_fpx
        rows      = db_all(room, 25)
        n         = db_count(room)
        tgt_dir   = dir_attr(tgt)
        tgt_style = rtl_style(tgt)
        tgt_font  = (
            "'Noto Naskh Arabic','Cairo',sans-serif"
            if tgt_dir == "rtl" else "'Cairo',sans-serif"
        )

        st.iframe(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.2}}}}
body{{margin:0;padding:2px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:7px;padding:8px 13px;
  background:#060606;border:1px solid #161616;border-radius:10px;
  font-size:11px;font-family:monospace;'>
  <span style='width:7px;height:7px;border-radius:50%;background:#00c65e;
    box-shadow:0 0 0 3px rgba(0,198,94,.15);
    animation:dp 1.4s infinite;flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    {esc(T("live_dot"))} · <b>{n}</b> {esc(T("segs"))} · {esc(T("room"))} <b>{esc(room)}</b> · <b>{esc(tgt.upper())}</b> · ↺{st.session_state.aud_rate}s
  </span>
</div>""", height=38)

        if not rows:
            st.iframe(PALETTE + f"""
<style>body{{padding:30px 0;text-align:center;background:transparent;}}</style>
<div style='font-size:42px;margin-bottom:9px'>⏳</div>
<div style='font-size:14px;color:#888;font-family:"Cairo","Noto Naskh Arabic",sans-serif;'>{esc(T("waiting"))}</div>
<div style='font-size:11px;color:#555;margin-top:5px;font-family:"Cairo","Noto Naskh Arabic",sans-serif;'>
  {esc(T("will_broadcast"))}</div>
""", height=150)
            return

        ltxt, llang, lts = rows[0]
        ltranslated = tr(ltxt, tgt, llang)

        src_dir   = dir_attr(llang)
        src_style = rtl_style(llang)
        src_font  = (
            "'Noto Naskh Arabic','Cairo',sans-serif"
            if src_dir == "rtl" else "'Cairo',sans-serif"
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

        js_translated = json.dumps(ltranslated)
        fs_align = "right" if tgt_dir == "rtl" else "left"

        st.iframe(PALETTE + f"""
<style>
body{{padding:5px 0 3px;background:transparent;}}
.stage{{
  background:#060606;border-radius:18px;
  padding:24px 20px;position:relative;overflow:hidden;
  display:flex;flex-direction:column;justify-content:center;min-height:120px;
}}
.border-glow{{
  position:absolute;inset:-1px;z-index:0;border-radius:18px;pointer-events:none;
  background:linear-gradient(135deg,rgba(206,17,38,.25),transparent 40%,rgba(0,122,61,.25));
}}
.stage::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);
  z-index:1;
}}
.so{{
  font-size:11px;color:#2a2a2a;font-style:italic;
  margin-bottom:9px;padding-bottom:9px;border-bottom:1px solid #111;
  line-height:1.6;position:relative;z-index:2;
}}
.st{{
  color:#f2ede3;font-weight:700;line-height:1.65;
  font-size:{fpx}px;animation:fi .4s ease;
  font-family:{tgt_font};
  {tgt_style}
  position:relative;z-index:2;
}}
@keyframes fi{{from{{opacity:.1;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
.sm{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#555;margin-top:11px;
  position:relative;z-index:2;}}
</style>
<div class="stage">
  <div class="border-glow"></div>
  {src_div}
  <div class="st" dir="{tgt_dir}">{esc(ltranslated)}</div>
  <div class="sm">🕐 {esc(lts)} · {esc((llang or "?").upper())} → {esc(tgt.upper())}</div>
</div>
""", height=max(175, fpx * 3 + 80))

        st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 5px;}}
.row{{display:flex;gap:8px;}}
.btn{{
  flex:1;background:#060606;border:1px solid #161616;border-radius:12px;
  padding:13px 8px;color:#333;font-size:12px;cursor:pointer;
  font-family:'Cairo',sans-serif;font-weight:700;text-align:center;
  -webkit-tap-highlight-color:transparent;transition:all .18s;
}}
.btn:active{{background:#161616;color:#f2ede3;transform:scale(.96);}}
.btn:hover{{background:#0a0a0a;color:#f2ede3;border-color:#007a3d;
  box-shadow:0 3px 12px rgba(0,122,61,.12);}}
#cm{{color:#00c65e;font-size:11px;opacity:0;transition:opacity .3s;align-self:center;}}
#fs{{display:none;position:fixed;inset:0;background:#000;z-index:99999;
  align-items:center;justify-content:center;cursor:pointer;
  flex-direction:column;text-align:{fs_align};padding:32px;}}
#fs-t{{
  color:#f2ede3;font-weight:700;line-height:1.45;
  font-size:clamp(28px,8vw,80px);max-width:95%;
  direction:{tgt_dir};font-family:{tgt_font};
}}
#fs-b{{position:absolute;bottom:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);}}
#fs-h{{position:absolute;bottom:20px;font-size:11px;color:#1a1a1a;font-family:monospace;}}
</style>
<div class="row">
  <button class="btn" onclick="speak()">{esc(T("speak_aloud"))}</button>
  <button class="btn" onclick="copy()">{esc(T("copy_btn"))}</button>
  <button class="btn" onclick="openfs()">{esc(T("full_btn"))}</button>
  <span id="cm">✓</span>
</div>
<div id="fs" onclick="closefs()">
  <div id="fs-t" dir="{tgt_dir}">{esc(ltranslated)}</div>
  <div id="fs-h">{esc(T("tap_close"))}</div>
  <div id="fs-b"></div>
</div>
<script>
const TX={js_translated}, L="{esc(tgt)}";
function speak(){{
  speechSynthesis.cancel();
  const u=new SpeechSynthesisUtterance(TX);
  u.lang=L;speechSynthesis.speak(u);
}}
function copy(){{
  navigator.clipboard.writeText(TX).then(()=>{{
    const m=document.getElementById('cm');
    m.style.opacity='1';
    setTimeout(()=>m.style.opacity='0',2000);
  }}).catch(()=>{{}});
  if(navigator.vibrate)navigator.vibrate(40);
}}
function openfs(){{document.getElementById('fs').style.display='flex';}}
function closefs(){{document.getElementById('fs').style.display='none';}}
</script>
""", height=58)

        older = rows[1:]
        if older:
            st.markdown(f"""
<div style='margin:6px 0 4px;font-size:10px;color:#555;text-align:center;
  font-family:monospace;letter-spacing:.12em;'>{esc(T("previous"))}</div>
""", unsafe_allow_html=True)

            h_html = ""
            for st_txt, sl, sts in older:
                s_tr   = tr(st_txt, tgt, sl)
                d2     = dir_attr(tgt)
                rs2    = rtl_style(tgt)
                f2     = (
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

            st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:2px 0 20px;}}
.ac{{background:#0d0d0d;border:1px solid #1e1e1e;border-radius:12px;
  padding:13px 15px;margin:5px 0;opacity:1;transition:all .2s;}}
.ac:hover{{border-color:#fd6b4b;box-shadow:0 0 0 1px rgba(253,107,75,.12);}}
.ao{{font-size:11px;color:#666;font-style:italic;margin-bottom:5px;line-height:1.6;}}
.at{{font-size:15px;font-weight:600;color:#c8c4bc;line-height:1.7;}}
.ats{{font-size:10px;color:#555;font-family:'JetBrains Mono',monospace;margin-top:5px;}}
</style>
{h_html}
""", height=min(60 + len(older) * 95, 1800))

    live_display()
