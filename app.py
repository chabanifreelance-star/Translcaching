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
        "tap_mic": "Tap mic · speak · tap again to send chunk",
        "speaking_lang": "Speaking language",
        "tap_hint": "🎙️  keep tapping · each recording adds to the live card",
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
        "chunks": "chunks",
        "room": "Room",
        "live_dot": "🔴 Live",
        "live_translation": "LIVE TRANSLATION",
        "original": "Original",
        "new_card": "🆕 New Card",
        "streaming": "● streaming",
        "sealed": "✓ done",
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
        "tap_mic": "Appuyez · parlez · chaque enregistrement s'ajoute",
        "speaking_lang": "Langue de discours",
        "tap_hint": "🎙️  continuez à appuyer · chaque chunk s'ajoute en direct",
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
        "chunks": "chunks",
        "room": "Salle",
        "live_dot": "🔴 En direct",
        "live_translation": "TRADUCTION EN DIRECT",
        "original": "Original",
        "new_card": "🆕 Nouvelle carte",
        "streaming": "● diffusion",
        "sealed": "✓ terminé",
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
        "tap_mic": "اضغط الميكروفون · كل تسجيل يُضاف للبطاقة الحية",
        "speaking_lang": "لغة الحديث",
        "tap_hint": "🎙️  استمر في الضغط · كل مقطع يُضاف مباشرة",
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
        "chunks": "مقطع",
        "room": "غرفة",
        "live_dot": "🔴 مباشر",
        "live_translation": "ترجمة فورية",
        "original": "النص الأصلي",
        "new_card": "🆕 بطاقة جديدة",
        "streaming": "● بث مباشر",
        "sealed": "✓ انتهى",
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
        "tap_mic": "Mikrofona bas · her kayıt canlı karta eklenir",
        "speaking_lang": "Konuşma dili",
        "tap_hint": "🎙️  basmaya devam et · her chunk canlı eklenir",
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
        "chunks": "parça",
        "room": "Oda",
        "live_dot": "🔴 Canlı",
        "live_translation": "CANLI ÇEVİRİ",
        "original": "Orijinal",
        "new_card": "🆕 Yeni Kart",
        "streaming": "● yayında",
        "sealed": "✓ bitti",
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
        "tap_mic": "Toca el micrófono · cada grabación se añade en vivo",
        "speaking_lang": "Idioma de habla",
        "tap_hint": "🎙️  sigue tocando · cada chunk se añade en directo",
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
        "chunks": "partes",
        "room": "Sala",
        "live_dot": "🔴 En vivo",
        "live_translation": "TRADUCCIÓN EN VIVO",
        "original": "Original",
        "new_card": "🆕 Nueva tarjeta",
        "streaming": "● en vivo",
        "sealed": "✓ listo",
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

# ── Database ──────────────────────────────────────────────────────────────────
DB = os.path.join(tempfile.gettempdir(), "lt_pal_v3.db")

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    with _cx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS rooms(
            code TEXT PRIMARY KEY, created TEXT NOT NULL)""")
        # card_id groups chunks belonging to one "speaking session"
        # sealed=1 means the speaker stopped (new card will start next time)
        c.execute("""CREATE TABLE IF NOT EXISTS chunks(
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            room      TEXT    NOT NULL,
            card_id   TEXT    NOT NULL,
            txt       TEXT    NOT NULL,
            lang      TEXT    DEFAULT '',
            sealed    INTEGER DEFAULT 0,
            ts        TEXT    NOT NULL)""")
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

def _check_rate_limit(room: str, max_per_minute: int = 60) -> bool:
    now = time.time()
    with _cx() as c:
        row = c.execute("SELECT last_save, count FROM rate_limit WHERE room=?", (room,)).fetchone()
        if row is None:
            c.execute("INSERT INTO rate_limit(room,last_save,count) VALUES(?,?,1)", (room, now))
            c.commit(); return True
        last_save, count = row
        if now - last_save > 60:
            c.execute("UPDATE rate_limit SET last_save=?, count=1 WHERE room=?", (now, room))
            c.commit(); return True
        if count >= max_per_minute:
            return False
        c.execute("UPDATE rate_limit SET count=count+1 WHERE room=?", (room,))
        c.commit(); return True

def chunk_save(room: str, card_id: str, txt: str, lang: str) -> bool:
    """Append a chunk to an open card."""
    try:
        if not _check_rate_limit(room):
            return False
        clean = txt.strip()[:2000]
        if not clean:
            return False
        with _cx() as c:
            c.execute(
                "INSERT INTO chunks(room,card_id,txt,lang,sealed,ts) VALUES(?,?,?,?,0,?)",
                (room, card_id, clean, lang, datetime.now().strftime("%H:%M")))
            c.commit()
        return True
    except Exception:
        return False

def card_seal(room: str, card_id: str):
    """Mark every chunk of this card as sealed (speaker stopped)."""
    try:
        with _cx() as c:
            c.execute("UPDATE chunks SET sealed=1 WHERE room=? AND card_id=?", (room, card_id))
            c.commit()
    except Exception:
        pass

def cards_get(room: str, limit: int = 8):
    """
    Return cards newest-first.
    Each card: (card_id, [(txt, lang, ts), ...], sealed)
    """
    try:
        if not re.fullmatch(r"[0-9]{4}", room or ""):
            return []
        with _cx() as c:
            # get distinct card_ids ordered by their latest chunk, newest first
            card_ids = c.execute(
                """SELECT card_id, MAX(id) as mx, MAX(sealed) as s
                   FROM chunks WHERE room=?
                   GROUP BY card_id ORDER BY mx DESC LIMIT ?""",
                (room, limit)).fetchall()
            result = []
            for cid, _, sealed in card_ids:
                rows = c.execute(
                    "SELECT txt,lang,ts FROM chunks WHERE room=? AND card_id=? ORDER BY id ASC",
                    (room, cid)).fetchall()
                result.append((cid, rows, bool(sealed)))
            return result
    except Exception:
        return []

def db_clear(room: str):
    if not re.fullmatch(r"[0-9]{4}", room or ""):
        return
    with _cx() as c:
        c.execute("DELETE FROM chunks WHERE room=?", (room,))
        c.commit()

def gen_code():
    return "".join(random.choices(string.digits, k=4))

init_db()

# ── Whisper ───────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_whisper_base():
    try:
        from faster_whisper import WhisperModel
        try:    return WhisperModel("small", device="cuda", compute_type="float16")
        except: return WhisperModel("small", device="cpu",  compute_type="int8")
    except: return None

@st.cache_resource(show_spinner=False)
def get_whisper_arabic():
    try:
        from faster_whisper import WhisperModel
        try:    return WhisperModel("small", device="cuda", compute_type="float16")
        except: return WhisperModel("small", device="cpu",  compute_type="int8")
    except: return None

_AR_HALLUCINATIONS = {
    "شكراً","شكرا","شكراً للمشاهدة","شكرا للمشاهدة",
    "للمشاهدة","للاستماع","مع السلامة","إلى اللقاء",
    "أراكم في الحلقة القادمة","تابعونا","اشتركوا في القناة",
    "سبحان الله","بسم الله الرحمن الرحيم","."," .","..","..."," ","",
}

def _is_hallucination(text: str, lang_code: str) -> bool:
    t = text.strip()
    if not t or len(t) < 2: return True
    if lang_code == "ar":
        if t in _AR_HALLUCINATIONS: return True
        if sum(1 for c in t if '\u0600' <= c <= '\u06FF') == 0: return True
    return False

def transcribe(audio_bytes: bytes, lang_code: str, room: str, card_id: str):
    """
    Transcribe audio; each Whisper segment is saved to DB immediately
    so the audience sees words growing in the live card in real-time.
    Returns full text.
    """
    is_arabic = lang_code == "ar"
    model = get_whisper_arabic() if is_arabic else get_whisper_base()
    if not model:
        model = get_whisper_base()
    if not model:
        return ""
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes); tmp = f.name
        if is_arabic:
            segs, _ = model.transcribe(
                tmp, task="transcribe", language="ar",
                beam_size=1, best_of=1, temperature=0.0,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                compression_ratio_threshold=2.0,
                log_prob_threshold=-0.8,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms":300,"speech_pad_ms":200,"threshold":0.45},
                initial_prompt="هذا نص باللغة العربية الفصحى.",
            )
            parts = []
            for s in segs:
                txt = s.text.strip()
                if _is_hallucination(txt, "ar"): continue
                if hasattr(s,'avg_logprob') and s.avg_logprob < -1.0: continue
                if hasattr(s,'compression_ratio') and s.compression_ratio > 2.4: continue
                parts.append(txt)
                chunk_save(room, card_id, txt, lang_code)
            return " ".join(parts).strip()
        else:
            segs, _ = model.transcribe(
                tmp, task="transcribe", language=lang_code,
                beam_size=5, vad_filter=True,
                condition_on_previous_text=False,
                vad_parameters={"min_silence_duration_ms":400},
            )
            parts = []
            for s in segs:
                txt = s.text.strip()
                if not txt: continue
                parts.append(txt)
                chunk_save(room, card_id, txt, lang_code)
            return " ".join(parts).strip()
    except Exception:
        return ""
    finally:
        if tmp:
            try: os.unlink(tmp)
            except: pass

# ── Translation ───────────────────────────────────────────────────────────────
_LANG_MAP = {"zh-cn":"zh-CN","zh-tw":"zh-TW","ar":"ar","he":"iw"}

def _norm_for_google(code: str) -> str:
    c = (code or "").strip()
    low = c.lower()
    if low in _LANG_MAP: return _LANG_MAP[low]
    if low.startswith("zh"): return c
    return low.split("-")[0]

_TR_CACHE: dict = {}
_TR_CACHE_MAX = 2000

def tr(text: str, target: str, source: str) -> str:
    if not text or not text.strip(): return text
    src = _norm_for_google(source)
    tgt = _norm_for_google(target)
    if src == tgt: return text
    cache_key = (text[:200], src, tgt)
    if cache_key in _TR_CACHE: return _TR_CACHE[cache_key]
    try:
        from deep_translator import GoogleTranslator
        use_src = "auto" if src in ("ar","iw","fa","ur") else src
        result = GoogleTranslator(source=use_src, target=tgt).translate(text)
        if not result or not result.strip():
            result = GoogleTranslator(source=src, target=tgt).translate(text)
        translated = result if result and result.strip() else text
    except Exception:
        translated = text
    if len(_TR_CACHE) >= _TR_CACHE_MAX:
        del _TR_CACHE[next(iter(_TR_CACHE))]
    _TR_CACHE[cache_key] = translated
    return translated

# ── Language lists ────────────────────────────────────────────────────────────
SPEAKER_LANGS = {
    "🇬🇧 English": "en",
    "🇸🇦 Arabic":  "ar",
}

AUDIENCE_LANGS = {
    "🇸🇦 Arabic":"ar",     "🇬🇧 English":"en",
    "🇫🇷 French":"fr",     "🇪🇸 Spanish":"es",
    "🇩🇪 German":"de",     "🇹🇷 Turkish":"tr",
    "🇮🇹 Italian":"it",    "🇨🇳 Chinese":"zh-CN",
    "🇷🇺 Russian":"ru",    "🇯🇵 Japanese":"ja",
    "🇧🇷 Portuguese":"pt", "🇮🇳 Hindi":"hi",
    "🇰🇷 Korean":"ko",     "🇳🇱 Dutch":"nl",
    "🇵🇱 Polish":"pl",     "🇸🇪 Swedish":"sv",
    "🇬🇷 Greek":"el",      "🇹🇭 Thai":"th",
    "🇻🇳 Vietnamese":"vi", "🇺🇦 Ukrainian":"uk",
    "🇮🇩 Indonesian":"id",
}

# ── Session state defaults ────────────────────────────────────────────────────
DEFAULTS = {
    "page":        "home",
    "room_code":   None,
    "last_hash":   None,
    # card_id: groups chunks from one continuous speaking session
    # Reset to None → next recording starts a new card
    "card_id":     None,
    "spk_lang":    "en",
    "aud_lang":    "ar",
    "aud_fpx":     28,
    "join_error":  "",
    "ui_lang":     "en",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(page, **kw):
    st.session_state.page = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()

# ── UI language toggle ────────────────────────────────────────────────────────
UI_LANG_OPTIONS = [
    ("🇬🇧 EN","en"),("🇫🇷 FR","fr"),("🇸🇦 AR","ar"),("🇹🇷 TR","tr"),("🇪🇸 ES","es"),
]

def render_lang_toggle():
    codes  = [c for _,c in UI_LANG_OPTIONS]
    labels = [l for l,_ in UI_LANG_OPTIONS]
    cur    = st.session_state.ui_lang
    cur_i  = codes.index(cur) if cur in codes else 0
    nxt_i  = (cur_i + 1) % len(codes)
    st.markdown("""<div style='height:6px'></div>""", unsafe_allow_html=True)
    col_l, col_btn, col_r = st.columns([3,2,3])
    with col_btn:
        if st.button(f"{labels[cur_i]}  →  {labels[nxt_i]}", key="lang_toggle", use_container_width=True):
            st.session_state.ui_lang = codes[nxt_i]
            st.rerun()
    st.markdown("""<div class='pal-divider'></div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    render_lang_toggle()
    rtl = is_rtl_ui()
    ui_dir   = "rtl" if rtl else "ltr"
    ui_align = "right" if rtl else "center"

    st.iframe(PALETTE + f"""
<style>
body{{
  display:flex;flex-direction:column;align-items:center;
  padding:16px 16px 12px;text-align:{ui_align};background:transparent;
  direction:{ui_dir};
}}
.kufic{{
  font-family:{("'Noto Naskh Arabic','Cairo'" if rtl else "'Bebas Neue'")};
  font-size:clamp({("44px,11vw,80px" if rtl else "60px,15vw,108px")});
  line-height:.85;letter-spacing:{(".02em" if rtl else ".03em")};
  font-weight:{("900" if rtl else "normal")};
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
  margin-top:12px;font-family:{("'Noto Naskh Arabic','Cairo'" if rtl else "'JetBrains Mono',monospace")};}}
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


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKER SETUP
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker_setup":

    if not st.session_state.room_code:
        code = gen_code()
        room_create(code)
        st.session_state.room_code = code

    code = st.session_state.room_code
    rtl  = is_rtl_ui()
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
.box{{background:#060606;border-radius:22px;padding:22px 40px 16px;}}
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
            c = gen_code(); room_create(c)
            st.session_state.room_code = c
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button(T("back_home"), key="spk_setup_back", use_container_width=True):
        go("home", room_code=None)


# ══════════════════════════════════════════════════════════════════════════════
# AUDIENCE JOIN
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience_join":

    rtl    = is_rtl_ui()
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


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKER
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":

    if not st.session_state.room_code:
        go("speaker_setup")

    room   = st.session_state.room_code
    rtl    = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    nl, nr = st.columns([3,1], gap="small")
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
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;
  margin-top:6px;font-family:'Cairo',sans-serif;}}
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

    # ── How chunking works ────────────────────────────────────────────────────
    # card_id is set when a recording arrives and cleared (→ None) when the
    # speaker clicks "New Card" or clears history.
    # Each mic tap appends to the SAME card_id so the audience sees one
    # growing card for the whole speaking session.
    # "New Card" button seals the current card and resets card_id so the
    # next recording starts a fresh card.

    st.markdown(f"""
<div style='background:rgba(0,122,61,.07);border:1px solid rgba(0,198,94,.12);
  border-radius:12px;padding:10px 14px;font-size:11px;color:#2a7a4a;
  text-align:center;font-family:monospace;letter-spacing:.05em;margin:4px 0 6px;'>
  🎙️ {esc(T("tap_hint"))}
</div>""", unsafe_allow_html=True)

    rec = st.audio_input("mic", key="mic_input", label_visibility="collapsed")

    if rec:
        audio_bytes = rec.read()
        h = hash(audio_bytes)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            lang_code = st.session_state.spk_lang

            # If no active card, create one
            if not st.session_state.card_id:
                st.session_state.card_id = datetime.now().strftime("%Y%m%d%H%M%S%f")

            card_id = st.session_state.card_id

            with st.spinner("Transcribing…"):
                txt = transcribe(audio_bytes, lang_code, room=room, card_id=card_id)

            if txt:
                st.rerun()
            else:
                st.warning("⚠️ No speech detected — try again.")

    # Controls row
    s1, s2, s3 = st.columns([3, 2, 2], gap="small")
    with s1:
        cards_data = cards_get(room, 1)
        active_card = cards_data[0] if cards_data else None
        chunk_count = len(active_card[1]) if active_card and not active_card[2] else 0
        status_txt = T("streaming") if (active_card and not active_card[2]) else T("sealed")
        status_col = "#00c65e" if (active_card and not active_card[2]) else "#555"
        st.iframe(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.25}}}}
body{{margin:0;padding:3px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:8px;padding:10px 14px;
  background:#060606;border:1px solid #161616;border-radius:10px;
  font-size:11px;font-family:monospace;'>
  <span style='width:7px;height:7px;border-radius:50%;background:{status_col};
    box-shadow:0 0 0 3px rgba(0,198,94,.18);
    animation:dp 1.4s infinite;flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    <b>{chunk_count}</b> {esc(T("chunks"))} · {esc(status_txt)} · {esc(T("room"))} <b>{esc(room)}</b>
  </span>
</div>""", height=44)
    with s2:
        if st.button(T("new_card"), key="new_card_btn", use_container_width=True):
            # Seal current card and reset so next recording starts fresh
            if st.session_state.card_id:
                card_seal(room, st.session_state.card_id)
            st.session_state.card_id = None
            st.rerun()
    with s3:
        if st.button(T("clear_btn"), key="clr_btn", use_container_width=True):
            db_clear(room)
            st.session_state.card_id = None
            st.rerun()

    # Show speaker's own transcript cards (newest first)
    all_cards = cards_get(room, 6)
    if not all_cards:
        st.iframe(PALETTE + f"""
<style>body{{padding:28px 0;text-align:center;background:transparent;}}</style>
<div style='font-size:38px;margin-bottom:8px;'>🎙️</div>
<div style='font-size:13px;color:#2a2a2a;font-family:"Cairo",sans-serif;'>
  {esc(T("nothing_yet"))}</div>
""", height=90)
    else:
        cards_html = ""
        for i, (cid, chunk_rows, sealed) in enumerate(all_cards):
            full_txt = " ".join(r[0] for r in chunk_rows if r[0].strip())
            lang     = chunk_rows[0][1] if chunk_rows else ""
            ts       = chunk_rows[-1][2] if chunk_rows else ""
            d        = dir_attr(lang)
            rs       = rtl_style(lang)
            tf       = ("'Noto Naskh Arabic','Cairo',sans-serif"
                        if dir_attr(lang) == "rtl" else "'Cairo',sans-serif")
            is_live  = (i == 0 and not sealed)
            border   = "border-left:3px solid #fd6b4b;" if is_live and d == "ltr" else \
                       ("border-right:3px solid #fd6b4b;" if is_live else "")
            bg       = "background:linear-gradient(135deg,rgba(253,107,75,.06),#080808 55%);" if is_live else ""
            badge    = f'<span class="ltag live">● LIVE</span>' if is_live else \
                       f'<span class="ltag done">✓</span>'
            n_chunks = len(chunk_rows)
            cards_html += f"""
<div class="hc" style="{border}{bg}">
  <div class="meta">
    <span class="ts">🕐 {esc(ts)}</span>
    <span class="ltag lang">{esc((lang or "??").upper())}</span>
    {badge}
    <span class="ts">{n_chunks} {esc(T("chunks"))}</span>
  </div>
  <div class="htxt" dir="{d}" style="{rs}font-family:{tf};">{esc(full_txt)}</div>
</div>"""

        st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 24px;}}
.hc{{background:#070707;border:1px solid #161616;border-radius:14px;
  padding:14px 16px;margin:5px 0;transition:border-color .2s;}}
.hc:hover{{border-color:#252525;}}
.meta{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:7px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#2a2a2a;}}
.ltag{{border-radius:5px;padding:1px 8px;font-size:9px;font-weight:700;
  letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ltag.lang{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);}}
.ltag.live{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);}}
.ltag.done{{background:rgba(85,85,85,.1);color:#555;border:1px solid rgba(85,85,85,.2);}}
.htxt{{font-size:15px;font-weight:600;color:#f2ede3;line-height:1.65;}}
</style>
{cards_html}
""", height=min(80 + len(all_cards) * 110, 2200))


# ══════════════════════════════════════════════════════════════════════════════
# AUDIENCE
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":

    if not st.session_state.room_code:
        go("audience_join")

    room   = st.session_state.room_code
    rtl    = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    al, ar_ = st.columns([3,1], gap="small")
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

    c1, c2 = st.columns([3,1], gap="small")
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
        if st.button("A−", key="fdn", use_container_width=True):
            st.session_state.aud_fpx = max(16, st.session_state.aud_fpx - 4)
        if st.button("A+", key="fup", use_container_width=True):
            st.session_state.aud_fpx = min(64, st.session_state.aud_fpx + 4)

    # Wake lock
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

    # ── Live display — polls every 1 second ───────────────────────────────────
    @st.fragment(run_every=1)
    def live_display():
        tgt      = st.session_state.aud_lang
        fpx      = st.session_state.aud_fpx
        tgt_dir  = dir_attr(tgt)
        tgt_sty  = rtl_style(tgt)
        tgt_font = ("'Noto Naskh Arabic','Cairo',sans-serif"
                    if tgt_dir == "rtl" else "'Cairo',sans-serif")
        fs_align = "right" if tgt_dir == "rtl" else "left"

        all_cards = cards_get(room, 6)

        # Status bar
        live_card = next((c for c in all_cards if not c[2]), None)
        is_live   = live_card is not None
        dot_col   = "#00c65e" if is_live else "#333"
        dot_anim  = "dp 1.2s infinite" if is_live else "none"
        status_lbl = T("streaming") if is_live else T("waiting")
        st.iframe(f"""
<style>
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.15}}}}
body{{margin:0;padding:2px 0;background:transparent;}}
</style>
<div style='display:flex;align-items:center;gap:7px;padding:8px 13px;
  background:#060606;border:1px solid #161616;border-radius:10px;
  font-size:11px;font-family:monospace;'>
  <span style='width:7px;height:7px;border-radius:50%;background:{dot_col};
    box-shadow:0 0 0 3px rgba(0,198,94,.15);
    animation:{dot_anim};flex-shrink:0;display:inline-block;'></span>
  <span style='color:#f2ede3;'>
    {esc(T("live_dot"))} · {esc(status_lbl)} · {esc(T("room"))} <b>{esc(room)}</b> · <b>{esc(tgt.upper())}</b>
  </span>
</div>""", height=38)

        if not all_cards:
            st.iframe(PALETTE + f"""
<style>body{{padding:30px 0;text-align:center;background:transparent;}}</style>
<div style='font-size:42px;margin-bottom:9px'>⏳</div>
<div style='font-size:14px;color:#888;font-family:"Cairo","Noto Naskh Arabic",sans-serif;'>
  {esc(T("waiting"))}</div>
<div style='font-size:11px;color:#555;margin-top:5px;font-family:"Cairo","Noto Naskh Arabic",sans-serif;'>
  {esc(T("will_broadcast"))}</div>
""", height=150)
            return

        # ── LIVE card (newest, not sealed) ────────────────────────────────────
        if live_card:
            cid, chunk_rows, _ = live_card
            src_lang = chunk_rows[0][1] if chunk_rows else ""
            last_ts  = chunk_rows[-1][2] if chunk_rows else ""

            # Translate each chunk individually (cached) then join
            tr_parts = []
            for chunk_txt, chunk_lang, _ in chunk_rows:
                t = tr(chunk_txt, tgt, chunk_lang)
                if t and t.strip():
                    tr_parts.append(t.strip())

            # All-but-last in white, latest chunk highlighted orange
            if len(tr_parts) > 1:
                prev_html = esc(" ".join(tr_parts[:-1])) + " "
            else:
                prev_html = ""
            new_html = esc(tr_parts[-1]) if tr_parts else ""

            full_tr   = " ".join(tr_parts)
            js_full   = json.dumps(full_tr)
            n_chunks  = len(chunk_rows)

            # Dynamic height
            char_count     = len(full_tr)
            chars_per_line = max(1, int(300 / (fpx * 0.55)))
            lines          = max(1, -(-char_count // chars_per_line))
            card_h         = max(180, lines * (fpx + 12) + 100)

            st.iframe(PALETTE + f"""
<style>
body{{padding:5px 0 3px;background:transparent;}}
.stage{{
  background:#060606;border-radius:18px;
  padding:22px 20px 18px;position:relative;overflow:hidden;
}}
.glow{{
  position:absolute;inset:-1px;z-index:0;border-radius:18px;pointer-events:none;
  background:linear-gradient(135deg,rgba(206,17,38,.22),transparent 40%,rgba(0,122,61,.22));
}}
.stage::after{{
  content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);
  z-index:1;
}}
.live-badge{{
  display:inline-flex;align-items:center;gap:5px;
  background:rgba(253,107,75,.1);border:1px solid rgba(253,107,75,.3);
  border-radius:6px;padding:2px 9px;margin-bottom:10px;
  font-size:10px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;
  font-weight:700;letter-spacing:.08em;position:relative;z-index:2;
}}
@keyframes bl{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.dot{{width:6px;height:6px;border-radius:50%;background:#ff8a6a;
  animation:bl 1s infinite;display:inline-block;}}
.body{{
  font-size:{fpx}px;font-weight:700;line-height:1.7;
  font-family:{tgt_font};
  {tgt_sty}
  position:relative;z-index:2;
  word-break:break-word;
}}
.body .old{{color:#f2ede3;}}
.body .new{{color:#fd6b4b;}}
@keyframes pop{{from{{opacity:.2;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.body .new{{animation:pop .3s ease;}}
.meta{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#333;
  margin-top:10px;position:relative;z-index:2;}}
</style>
<div class="stage">
  <div class="glow"></div>
  <div class="live-badge"><span class="dot"></span> LIVE · {n_chunks} {esc(T("chunks"))}</div>
  <div class="body" dir="{tgt_dir}">
    <span class="old">{prev_html}</span><span class="new">{new_html}</span>
  </div>
  <div class="meta">🕐 {esc(last_ts)} · {esc(src_lang.upper())} → {esc(tgt.upper())}</div>
</div>
""", height=card_h)

            # Action buttons
            st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 5px;}}
.row{{display:flex;gap:8px;}}
.btn{{
  flex:1;background:#060606;border:1px solid #161616;border-radius:12px;
  padding:12px 8px;color:#333;font-size:12px;cursor:pointer;
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
  color:#f2ede3;font-weight:700;line-height:1.55;
  font-size:clamp(24px,6vw,60px);max-width:95%;
  direction:{tgt_dir};font-family:{tgt_font};
  word-break:break-word;
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
  <div id="fs-t" dir="{tgt_dir}">{esc(full_tr)}</div>
  <div id="fs-h">{esc(T("tap_close"))}</div>
  <div id="fs-b"></div>
</div>
<script>
const TX={js_full},L="{esc(tgt)}";
function speak(){{speechSynthesis.cancel();const u=new SpeechSynthesisUtterance(TX);u.lang=L;speechSynthesis.speak(u);}}
function copy(){{navigator.clipboard.writeText(TX).then(()=>{{const m=document.getElementById('cm');m.style.opacity='1';setTimeout(()=>m.style.opacity='0',2000);}}).catch(()=>{{}});if(navigator.vibrate)navigator.vibrate(40);}}
function openfs(){{document.getElementById('fs').style.display='flex';}}
function closefs(){{document.getElementById('fs').style.display='none';}}
</script>
""", height=56)

        # ── SEALED previous cards ─────────────────────────────────────────────
        sealed_cards = [c for c in all_cards if c[2]]
        if sealed_cards:
            st.markdown(f"""
<div style='margin:8px 0 4px;font-size:10px;color:#444;text-align:center;
  font-family:monospace;letter-spacing:.12em;'>{esc(T("previous"))}</div>
""", unsafe_allow_html=True)

            prev_html = ""
            for cid, chunk_rows, _ in sealed_cards:
                if not chunk_rows: continue
                src_lang = chunk_rows[0][1]
                ts       = chunk_rows[-1][2]
                tr_parts = []
                for ct, cl, _ in chunk_rows:
                    t = tr(ct, tgt, cl)
                    if t and t.strip(): tr_parts.append(t.strip())
                full_tr = " ".join(tr_parts)
                d2  = dir_attr(tgt)
                rs2 = rtl_style(tgt)
                tf2 = ("'Noto Naskh Arabic','Cairo',sans-serif"
                       if d2 == "rtl" else "'Cairo',sans-serif")
                prev_html += f"""
<div class="pc">
  <div class="at" dir="{d2}" style="{rs2}font-family:{tf2};">{esc(full_tr)}</div>
  <div class="ats">🕐 {esc(ts)} · {esc(src_lang.upper())} → {esc(tgt.upper())} · {len(chunk_rows)} {esc(T("chunks"))}</div>
</div>"""

            sealed_h = min(50 + len(sealed_cards) * 100, 1600)
            st.iframe(PALETTE + f"""
<style>
body{{background:transparent;padding:2px 0 20px;}}
.pc{{background:#0d0d0d;border:1px solid #1a1a1a;border-radius:14px;
  padding:14px 16px;margin:5px 0;transition:border-color .2s;}}
.pc:hover{{border-color:#2a2a2a;}}
.at{{font-size:15px;font-weight:600;color:#888;line-height:1.7;word-break:break-word;}}
.ats{{font-size:10px;color:#333;font-family:'JetBrains Mono',monospace;margin-top:6px;}}
</style>
{prev_html}
""", height=sealed_h)

    live_display()
