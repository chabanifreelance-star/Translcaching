"""
LiveTranslate — Web Speech API edition
=======================================
Architecture
  Speaker browser  →  Web Speech API (word-by-word)
                   →  POST /api/chunk   (every interim/final result)
                   →  SQLite
  Audience browser →  GET  /api/poll?room=XXXX&since=ID
                   →  renders translated chunks in real time (1-second polling)

The HTTP micro-server runs in a daemon thread inside the Streamlit process so
there is NO separate server process to manage.  It listens on a fixed port
(default 7861) and is reachable by both the speaker and audience browsers
because they are on the same host as the Streamlit server.
"""

import streamlit as st
import sqlite3, os, tempfile, random, string, html, re, time, json, threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

# ─────────────────────────────────────────────────────────────────────────────
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

# ─── API port (configurable via env) ─────────────────────────────────────────
API_PORT = int(os.environ.get("LIVETRANSLATE_API_PORT", "7861"))

# ─── i18n strings ─────────────────────────────────────────────────────────────
UI_STRINGS = {
    "en": {
        "hero_line1": "LIVE", "hero_line2": "TRANSLATE",
        "app_sub": "Real-time multilingual subtitles",
        "speaker_btn": "🎤  SPEAKER", "audience_btn": "👥  AUDIENCE",
        "footer": "Web Speech API · deep-translator · 100% free",
        "your_room": "YOUR ROOM", "share_code": "Share this code with your audience",
        "room_code_lbl": "🔑 Room Code", "code_hint": "Tell your audience to enter this code",
        "enter_speak": "🎤  Enter Room & Speak", "new_code": "🔄  New Code",
        "back_home": "← Back to Home", "join_room": "JOIN ROOM",
        "enter_code": "Enter the 4-digit code from the speaker",
        "join_btn": "👥  Join Room", "back": "← Back",
        "ask_speaker": "Ask the <b>Speaker</b> for the 4-digit room code.<br>Each room is private.",
        "speak_now": "SPEAK NOW", "tap_mic": "Tap mic to START · speak freely · tap again to STOP",
        "speaking_lang": "Speaking language",
        "tap_hint": "🎙️  Tap the microphone to start · tap again to stop",
        "home_btn": "← Home", "clear_btn": "🗑 Clear",
        "nothing_yet": "Nothing yet — tap the microphone above",
        "live_subs": "LIVE SUBS", "realtime_subs": "Real-time translated subtitles",
        "language": "Language", "refresh": "Refresh", "waiting": "Waiting for speaker…",
        "will_broadcast": "The speaker will broadcast to this room",
        "speak_aloud": "🔊 Aloud", "copy_btn": "📋 Copy", "full_btn": "⛶ Full",
        "tap_close": "Tap to close", "previous": "─── PREVIOUS ───",
        "font": "font", "chunks": "chunks", "room": "Room", "live_dot": "🔴 Live",
        "streaming": "● streaming", "sealed": "✓ done",
        "recording": "● LIVE", "new_card": "🆕 New Card",
        "mic_start": "🎤 START", "mic_stop": "⏹ STOP",
        "mic_unsupported": "⚠️ Your browser does not support the Web Speech API. Please use Chrome or Edge.",
        "mic_denied": "⚠️ Microphone permission denied. Please allow microphone access.",
        "original": "Original",
    },
    "fr": {
        "hero_line1": "LIVE", "hero_line2": "TRADUCTION",
        "app_sub": "Multilingues en temps réel",
        "speaker_btn": "🎤  ORATEUR", "audience_btn": "👥  AUDIENCE",
        "footer": "Web Speech API · deep-translator · 100% gratuit",
        "your_room": "VOTRE SALLE", "share_code": "Partagez ce code avec votre audience",
        "room_code_lbl": "🔑 Code de salle", "code_hint": "Dites à votre audience d'entrer ce code",
        "enter_speak": "🎤  Entrer & Parler", "new_code": "🔄  Nouveau Code",
        "back_home": "← Retour à l'accueil", "join_room": "REJOINDRE",
        "enter_code": "Entrez le code 4 chiffres du conférencier",
        "join_btn": "👥  Rejoindre", "back": "← Retour",
        "ask_speaker": "Demandez le code 4 chiffres au <b>Conférencier</b>.<br>Chaque salle est privée.",
        "speak_now": "PARLEZ MAINTENANT", "tap_mic": "Appuyez sur le micro pour DÉMARRER",
        "speaking_lang": "Langue de discours",
        "tap_hint": "🎙️  Appuyez sur le micro pour commencer",
        "home_btn": "← Accueil", "clear_btn": "🗑 Effacer",
        "nothing_yet": "Rien encore — appuyez sur le micro",
        "live_subs": "SOUS-TITRES", "realtime_subs": "Sous-titres traduits en temps réel",
        "language": "Langue", "refresh": "Rafraîchir", "waiting": "En attente du conférencier…",
        "will_broadcast": "Le conférencier diffusera dans cette salle",
        "speak_aloud": "🔊 À voix haute", "copy_btn": "📋 Copier", "full_btn": "⛶ Plein",
        "tap_close": "Appuyer pour fermer", "previous": "─── PRÉCÉDENT ───",
        "font": "police", "chunks": "chunks", "room": "Salle", "live_dot": "🔴 En direct",
        "streaming": "● diffusion", "sealed": "✓ terminé",
        "recording": "● EN DIRECT", "new_card": "🆕 Nouvelle carte",
        "mic_start": "🎤 DÉMARRER", "mic_stop": "⏹ ARRÊTER",
        "mic_unsupported": "⚠️ Votre navigateur ne supporte pas Web Speech API. Utilisez Chrome.",
        "mic_denied": "⚠️ Permission microphone refusée.",
        "original": "Original",
    },
    "ar": {
        "hero_line1": "مباشر", "hero_line2": "ترجمة",
        "app_sub": "ترجمة فورية متعددة اللغات",
        "speaker_btn": "🎤  المتحدث", "audience_btn": "👥  الجمهور",
        "footer": "Web Speech API · deep-translator · مجاني 100%",
        "your_room": "غرفتك", "share_code": "شارك هذا الرمز مع جمهورك",
        "room_code_lbl": "🔑 رمز الغرفة", "code_hint": "أخبر جمهورك بإدخال هذا الرمز",
        "enter_speak": "🎤  ادخل الغرفة وتحدث", "new_code": "🔄  رمز جديد",
        "back_home": "→ العودة للرئيسية", "join_room": "انضم للغرفة",
        "enter_code": "أدخل الرمز المكون من 4 أرقام من المتحدث",
        "join_btn": "👥  انضم", "back": "→ رجوع",
        "ask_speaker": "اطلب من <b>المتحدث</b> رمز الغرفة.",
        "speak_now": "تحدث الآن", "tap_mic": "اضغط الميكروفون للبدء",
        "speaking_lang": "لغة الحديث",
        "tap_hint": "🎙️  اضغط الميكروفون للبدء",
        "home_btn": "→ الرئيسية", "clear_btn": "🗑 مسح",
        "nothing_yet": "لا شيء بعد — اضغط الميكروفون",
        "live_subs": "ترجمة مباشرة", "realtime_subs": "ترجمة فورية في الوقت الحقيقي",
        "language": "اللغة", "refresh": "تحديث", "waiting": "في انتظار المتحدث…",
        "will_broadcast": "سيبث المتحدث في هذه الغرفة",
        "speak_aloud": "🔊 تشغيل", "copy_btn": "📋 نسخ", "full_btn": "⛶ ملء الشاشة",
        "tap_close": "اضغط للإغلاق", "previous": "─── السابق ───",
        "font": "خط", "chunks": "مقطع", "room": "غرفة", "live_dot": "🔴 مباشر",
        "streaming": "● بث مباشر", "sealed": "✓ انتهى",
        "recording": "● مباشر", "new_card": "🆕 بطاقة جديدة",
        "mic_start": "🎤 ابدأ", "mic_stop": "⏹ إيقاف",
        "mic_unsupported": "⚠️ متصفحك لا يدعم Web Speech API. استخدم Chrome.",
        "mic_denied": "⚠️ تم رفض إذن الميكروفون.",
        "original": "النص الأصلي",
    },
    "tr": {
        "hero_line1": "CANLI", "hero_line2": "ÇEVİRİ",
        "app_sub": "Gerçek zamanlı çok dilli altyazılar",
        "speaker_btn": "🎤  KONUŞMACI", "audience_btn": "👥  KATİLİMCILAR",
        "footer": "Web Speech API · deep-translator · 100% ücretsiz",
        "your_room": "ODANIZ", "share_code": "Bu kodu izleyicilerinizle paylaşın",
        "room_code_lbl": "🔑 Oda Kodu", "code_hint": "İzleyicilerinize bu kodu girin deyin",
        "enter_speak": "🎤  Odaya Gir & Konuş", "new_code": "🔄  Yeni Kod",
        "back_home": "← Ana Sayfaya Dön", "join_room": "ODAYA KATIL",
        "enter_code": "Konuşmacının 4 haneli kodunu girin",
        "join_btn": "👥  Katıl", "back": "← Geri",
        "ask_speaker": "<b>Konuşmacıdan</b> 4 haneli oda kodunu isteyin.",
        "speak_now": "KONUŞUN", "tap_mic": "Mikrofona bas · konuş · tekrar bas",
        "speaking_lang": "Konuşma dili",
        "tap_hint": "🎙️  Mikrofona dokun · konuş · tekrar dokun",
        "home_btn": "← Ana Sayfa", "clear_btn": "🗑 Temizle",
        "nothing_yet": "Henüz bir şey yok — mikrofona dokunun",
        "live_subs": "CANLI ALTYAZI", "realtime_subs": "Gerçek zamanlı çevrilmiş altyazılar",
        "language": "Dil", "refresh": "Yenile", "waiting": "Konuşmacı bekleniyor…",
        "will_broadcast": "Konuşmacı bu odaya yayın yapacak",
        "speak_aloud": "🔊 Sesli", "copy_btn": "📋 Kopyala", "full_btn": "⛶ Tam Ekran",
        "tap_close": "Kapatmak için dokun", "previous": "─── ÖNCEKİ ───",
        "font": "yazı tipi", "chunks": "parça", "room": "Oda", "live_dot": "🔴 Canlı",
        "streaming": "● yayında", "sealed": "✓ bitti",
        "recording": "● CANLI", "new_card": "🆕 Yeni Kart",
        "mic_start": "🎤 BAŞLAT", "mic_stop": "⏹ DURDUR",
        "mic_unsupported": "⚠️ Tarayıcınız Web Speech API'yi desteklemiyor. Chrome kullanın.",
        "mic_denied": "⚠️ Mikrofon izni reddedildi.",
        "original": "Orijinal",
    },
    "es": {
        "hero_line1": "EN VIVO", "hero_line2": "TRADUCIR",
        "app_sub": "Subtítulos multilingües en tiempo real",
        "speaker_btn": "🎤  ORADOR", "audience_btn": "👥  AUDIENCIA",
        "footer": "Web Speech API · deep-translator · 100% gratis",
        "your_room": "TU SALA", "share_code": "Comparte este código con tu audiencia",
        "room_code_lbl": "🔑 Código de sala", "code_hint": "Dile a tu audiencia que ingrese este código",
        "enter_speak": "🎤  Entrar & Hablar", "new_code": "🔄  Nuevo Código",
        "back_home": "← Volver al inicio", "join_room": "UNIRSE A SALA",
        "enter_code": "Ingresa el código de 4 dígitos del orador",
        "join_btn": "👥  Unirse", "back": "← Atrás",
        "ask_speaker": "Pide al <b>Orador</b> el código de sala de 4 dígitos.",
        "speak_now": "HABLA AHORA", "tap_mic": "Toca el micrófono para INICIAR",
        "speaking_lang": "Idioma de habla",
        "tap_hint": "🎙️  Toca el micrófono para iniciar",
        "home_btn": "← Inicio", "clear_btn": "🗑 Limpiar",
        "nothing_yet": "Nada todavía — toca el micrófono arriba",
        "live_subs": "SUBTÍTULOS", "realtime_subs": "Subtítulos traducidos en tiempo real",
        "language": "Idioma", "refresh": "Refrescar", "waiting": "Esperando al orador…",
        "will_broadcast": "El orador transmitirá a esta sala",
        "speak_aloud": "🔊 En voz alta", "copy_btn": "📋 Copiar", "full_btn": "⛶ Pantalla completa",
        "tap_close": "Toca para cerrar", "previous": "─── ANTERIORES ───",
        "font": "fuente", "chunks": "partes", "room": "Sala", "live_dot": "🔴 En vivo",
        "streaming": "● en vivo", "sealed": "✓ listo",
        "recording": "● EN VIVO", "new_card": "🆕 Nueva tarjeta",
        "mic_start": "🎤 INICIAR", "mic_stop": "⏹ DETENER",
        "mic_unsupported": "⚠️ Tu navegador no soporta Web Speech API. Usa Chrome.",
        "mic_denied": "⚠️ Permiso de micrófono denegado.",
        "original": "Original",
    },
}

def T(key: str) -> str:
    lang = st.session_state.get("ui_lang", "en")
    return UI_STRINGS.get(lang, UI_STRINGS["en"]).get(key, UI_STRINGS["en"].get(key, key))

def is_rtl_ui() -> bool:
    return st.session_state.get("ui_lang", "en") == "ar"

# ─────────────────────────────────────────────────────────────────────────────
# Database
# ─────────────────────────────────────────────────────────────────────────────
DB = os.path.join(tempfile.gettempdir(), "lt_webspeech_v1.db")
_db_lock = threading.Lock()

def _cx():
    return sqlite3.connect(DB, check_same_thread=False, timeout=10)

def init_db():
    with _cx() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS rooms(
            code TEXT PRIMARY KEY, created TEXT NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS chunks(
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            room      TEXT    NOT NULL,
            card_id   TEXT    NOT NULL,
            txt       TEXT    NOT NULL,
            lang      TEXT    DEFAULT '',
            interim   INTEGER DEFAULT 0,
            sealed    INTEGER DEFAULT 0,
            ts        TEXT    NOT NULL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS rate_limit(
            room TEXT PRIMARY KEY, last_save REAL NOT NULL, count INTEGER DEFAULT 0)""")
        # index for fast audience polling
        c.execute("CREATE INDEX IF NOT EXISTS idx_chunks_room_id ON chunks(room,id)")
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

def _check_rate_limit(room: str, max_per_minute: int = 120) -> bool:
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

def chunk_upsert(room: str, card_id: str, chunk_id: str,
                 txt: str, lang: str, interim: bool) -> int | None:
    """
    Insert or replace a chunk.  chunk_id is a client-generated key like
    card_id + ':' + sequence_number.  Returns the row id on success.
    """
    if not _check_rate_limit(room):
        return None
    clean = txt.strip()[:2000]
    if not clean:
        return None
    ts = datetime.now().strftime("%H:%M:%S")
    with _db_lock, _cx() as c:
        # delete previous interim for the same logical slot (overwrite)
        if interim:
            c.execute(
                "DELETE FROM chunks WHERE room=? AND card_id=? AND chunk_id=? AND interim=1",
                (room, card_id, chunk_id))
        c.execute(
            """INSERT INTO chunks(room,card_id,chunk_id,txt,lang,interim,sealed,ts)
               VALUES(?,?,?,?,?,?,0,?)
               ON CONFLICT(room,card_id,chunk_id) DO UPDATE SET
                 txt=excluded.txt, lang=excluded.lang,
                 interim=excluded.interim, ts=excluded.ts""",
            (room, card_id, chunk_id, clean, lang, 1 if interim else 0, ts))
        c.commit()
        row = c.execute("SELECT id FROM chunks WHERE room=? AND card_id=? AND chunk_id=?",
                        (room, card_id, chunk_id)).fetchone()
        return row[0] if row else None

def card_seal(room: str, card_id: str):
    with _db_lock, _cx() as c:
        c.execute("UPDATE chunks SET sealed=1 WHERE room=? AND card_id=?", (room, card_id))
        c.commit()

def poll_chunks(room: str, since_id: int, limit: int = 50):
    """Return chunks newer than since_id for audience polling."""
    with _cx() as c:
        rows = c.execute(
            """SELECT id, card_id, txt, lang, interim, sealed, ts
               FROM chunks WHERE room=? AND id>?
               ORDER BY id ASC LIMIT ?""",
            (room, since_id, limit)).fetchall()
    return [{"id": r[0], "card_id": r[1], "txt": r[2], "lang": r[3],
             "interim": bool(r[4]), "sealed": bool(r[5]), "ts": r[6]}
            for r in rows]

def cards_get(room: str, limit: int = 8):
    """Return cards for the speaker view (list of (card_id, rows, sealed))."""
    with _cx() as c:
        card_ids = c.execute(
            """SELECT card_id, MAX(id) as mx, MAX(sealed) as s
               FROM chunks WHERE room=?
               GROUP BY card_id ORDER BY mx DESC LIMIT ?""",
            (room, limit)).fetchall()
        result = []
        for cid, _, sealed in card_ids:
            rows = c.execute(
                "SELECT txt,lang,ts,interim FROM chunks WHERE room=? AND card_id=? ORDER BY id ASC",
                (room, cid)).fetchall()
            result.append((cid, rows, bool(sealed)))
        return result

def db_clear(room: str):
    if not re.fullmatch(r"[0-9]{4}", room or ""):
        return
    with _db_lock, _cx() as c:
        c.execute("DELETE FROM chunks WHERE room=?", (room,))
        c.execute("DELETE FROM rate_limit WHERE room=?", (room,))
        c.commit()

def gen_code():
    return "".join(random.choices(string.digits, k=4))

init_db()

# ─────────────────────────────────────────────────────────────────────────────
# Add chunk_id column if upgrading from old schema
# ─────────────────────────────────────────────────────────────────────────────
try:
    with _cx() as c:
        c.execute("ALTER TABLE chunks ADD COLUMN chunk_id TEXT DEFAULT ''")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_chunk_unique ON chunks(room,card_id,chunk_id)")
        c.commit()
except Exception:
    pass

# ─────────────────────────────────────────────────────────────────────────────
# Translation
# ─────────────────────────────────────────────────────────────────────────────
_LANG_MAP = {"zh-cn": "zh-CN", "zh-tw": "zh-TW", "ar": "ar", "he": "iw"}

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
        use_src = "auto" if src in ("ar", "iw", "fa", "ur") else src
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

# ─────────────────────────────────────────────────────────────────────────────
# Embedded HTTP micro-server  (runs in a daemon thread)
# ─────────────────────────────────────────────────────────────────────────────
class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass  # silence access logs

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)

        if parsed.path == "/api/poll":
            room = sanitize_code((qs.get("room", [""])[0]))
            since = int(qs.get("since", ["0"])[0])
            tgt   = (qs.get("tgt", ["en"])[0])[:10]
            if not re.fullmatch(r"[0-9]{4}", room):
                self._send_json({"error": "bad room"}, 400); return
            chunks = poll_chunks(room, since)
            # translate on the fly
            for ch in chunks:
                src_lang = ch["lang"] or "en"
                ch["translated"] = tr(ch["txt"], tgt, src_lang)
            self._send_json({"chunks": chunks})

        elif parsed.path == "/api/ping":
            self._send_json({"ok": True})

        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""

        if parsed.path == "/api/chunk":
            try:
                data = json.loads(body)
                room    = sanitize_code(data.get("room", ""))
                card_id = str(data.get("card_id", ""))[:40]
                chunk_id = str(data.get("chunk_id", ""))[:80]
                txt     = str(data.get("txt", ""))
                lang    = str(data.get("lang", "en"))[:10]
                interim = bool(data.get("interim", False))
                if not re.fullmatch(r"[0-9]{4}", room) or not txt.strip():
                    self._send_json({"error": "bad data"}, 400); return
                row_id = chunk_upsert(room, card_id, chunk_id, txt, lang, interim)
                self._send_json({"ok": True, "id": row_id})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif parsed.path == "/api/seal":
            try:
                data = json.loads(body)
                room    = sanitize_code(data.get("room", ""))
                card_id = str(data.get("card_id", ""))[:40]
                if re.fullmatch(r"[0-9]{4}", room):
                    card_seal(room, card_id)
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif parsed.path == "/api/clear":
            try:
                data = json.loads(body)
                room = sanitize_code(data.get("room", ""))
                if re.fullmatch(r"[0-9]{4}", room):
                    db_clear(room)
                self._send_json({"ok": True})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        else:
            self.send_response(404); self.end_headers()


def _start_api_server():
    """Start the HTTP API on API_PORT in a background daemon thread."""
    try:
        server = HTTPServer(("0.0.0.0", API_PORT), _Handler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return True
    except OSError:
        # Port already in use — already running from a previous Streamlit rerun
        return False

# Only start once per process
if "api_server_started" not in st.session_state:
    _start_api_server()
    st.session_state["api_server_started"] = True

API_BASE = f"http://localhost:{API_PORT}"

# ─────────────────────────────────────────────────────────────────────────────
# Global CSS + PALETTE
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=Noto+Naskh+Arabic:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

#MainMenu,header,footer,
[data-testid="stSidebar"],[data-testid="collapsedControl"],
[data-testid="stStatusWidget"]{display:none!important;}

.stApp{background:#050505!important;}
.block-container{padding:0!important;max-width:100%!important;}
body,html{overflow-x:hidden!important;}

.stButton>button{
  background:linear-gradient(135deg,#0a0a0a,#111)!important;
  border:1px solid #222!important;color:#f2ede3!important;
  border-radius:14px!important;font-weight:700!important;font-size:13px!important;
  padding:12px 8px!important;width:100%!important;
  font-family:'Cairo',sans-serif!important;letter-spacing:.04em!important;
  transition:all .2s cubic-bezier(.4,0,.2,1)!important;
}
.stButton>button:hover{
  background:linear-gradient(135deg,#111,#181818)!important;
  border-color:#007a3d!important;transform:translateY(-1px)!important;
  box-shadow:0 4px 20px rgba(0,122,61,.18)!important;
}
.stTextInput>div>div>input{
  background:#080808!important;border:1px solid #222!important;color:#f2ede3!important;
  border-radius:14px!important;font-size:24px!important;text-align:center!important;
  letter-spacing:10px!important;font-weight:700!important;
  font-family:'JetBrains Mono',monospace!important;padding:16px!important;
}
.stTextInput>div>div>input:focus{border-color:#007a3d!important;}
.stSelectbox>div>div{background:#080808!important;border:1px solid #222!important;border-radius:12px!important;color:#f2ede3!important;}
iframe{display:block!important;}
div[data-testid="stVerticalBlockBorderWrapper"]{padding:0!important;}
.pal-divider{height:3px;background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%,#007a3d 100%);border-radius:3px;margin:6px 0;}
</style>
""", unsafe_allow_html=True)

PALETTE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=Noto+Naskh+Arabic:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
:root{--bg:#050505;--card:#080808;--b:#1a1a1a;--b2:#252525;
  --white:#f2ede3;--dim:#222;--green:#007a3d;--gl:#00c65e;
  --red:#ce1126;--rl:#ff3348;--black:#000;--melon:#fd6b4b;--ml:#ff8a6a;}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{background:transparent;color:var(--white);
  font-family:'Cairo','Noto Naskh Arabic',sans-serif;-webkit-font-smoothing:antialiased;overflow-x:hidden;}
</style>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Session state
# ─────────────────────────────────────────────────────────────────────────────
AUDIENCE_LANGS = {
    "🇸🇦 Arabic":"ar","🇬🇧 English":"en","🇫🇷 French":"fr","🇪🇸 Spanish":"es",
    "🇩🇪 German":"de","🇹🇷 Turkish":"tr","🇮🇹 Italian":"it","🇨🇳 Chinese":"zh-CN",
    "🇷🇺 Russian":"ru","🇯🇵 Japanese":"ja","🇧🇷 Portuguese":"pt","🇮🇳 Hindi":"hi",
    "🇰🇷 Korean":"ko","🇳🇱 Dutch":"nl","🇵🇱 Polish":"pl","🇸🇪 Swedish":"sv",
    "🇬🇷 Greek":"el","🇹🇭 Thai":"th","🇻🇳 Vietnamese":"vi","🇺🇦 Ukrainian":"uk",
    "🇮🇩 Indonesian":"id",
}
SPEAKER_LANGS = {
    "🇬🇧 English":"en","🇸🇦 Arabic":"ar","🇫🇷 French":"fr","🇪🇸 Spanish":"es",
    "🇩🇪 German":"de","🇹🇷 Turkish":"tr","🇮🇹 Italian":"it","🇨🇳 Chinese":"zh-CN",
    "🇷🇺 Russian":"ru","🇯🇵 Japanese":"ja","🇧🇷 Portuguese":"pt","🇰🇷 Korean":"ko",
}

DEFAULTS = {
    "page": "home", "room_code": None, "card_id": None,
    "spk_lang": "en", "aud_lang": "ar", "aud_fpx": 28,
    "join_error": "", "ui_lang": "en",
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def go(page, **kw):
    st.session_state.page = page
    for k, v in kw.items():
        st.session_state[k] = v
    st.rerun()

UI_LANG_OPTIONS = [("🇬🇧 EN","en"),("🇫🇷 FR","fr"),("🇸🇦 AR","ar"),("🇹🇷 TR","tr"),("🇪🇸 ES","es")]

def render_lang_toggle():
    codes  = [c for _,c in UI_LANG_OPTIONS]
    labels = [l for l,_ in UI_LANG_OPTIONS]
    cur    = st.session_state.ui_lang
    cur_i  = codes.index(cur) if cur in codes else 0
    nxt_i  = (cur_i + 1) % len(codes)
    st.markdown("""<div style='height:6px'></div>""", unsafe_allow_html=True)
    _, col_btn, _ = st.columns([3,2,3])
    with col_btn:
        if st.button(f"{labels[cur_i]}  →  {labels[nxt_i]}", key="lang_toggle", use_container_width=True):
            st.session_state.ui_lang = codes[nxt_i]; st.rerun()
    st.markdown("""<div class='pal-divider'></div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":
    render_lang_toggle()
    rtl = is_rtl_ui()
    ui_dir   = "rtl" if rtl else "ltr"
    ui_align = "right" if rtl else "center"

    st.components.v1.html(PALETTE + f"""
<style>
body{{display:flex;flex-direction:column;align-items:center;
  padding:16px 16px 12px;text-align:{ui_align};background:transparent;direction:{ui_dir};}}
.kufic{{font-family:{("'Noto Naskh Arabic','Cairo'" if rtl else "'Bebas Neue'")};
  font-size:clamp({("44px,11vw,80px" if rtl else "60px,15vw,108px")});
  line-height:.85;letter-spacing:.03em;font-weight:{("900" if rtl else "normal")};}}
.live-word{{background:linear-gradient(135deg,#ff3348 0%,#fd6b4b 45%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.tr-word{{background:linear-gradient(135deg,#fd6b4b 0%,#ff8a6a 55%,#fff 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:11px;color:#666;letter-spacing:.14em;text-transform:uppercase;
  margin-top:12px;font-family:{("'Noto Naskh Arabic','Cairo'" if rtl else "'JetBrains Mono',monospace")};}}
.pal-bar{{display:flex;width:86%;max-width:310px;height:4px;border-radius:4px;overflow:hidden;margin:14px auto 0;}}
.pb-r{{flex:1;background:#fd6b4b;}}.pb-m{{flex:1;background:#ff8a6a;}}
.pb-d{{flex:1;background:#e85530;}}.pb-w{{flex:1;background:#ce1126;}}
</style>
<div class="kufic">
  <span class="live-word">{esc(T("hero_line1"))}</span><br>
  <span class="tr-word">{esc(T("hero_line2"))}</span>
</div>
<div class="sub">{esc(T("app_sub"))} 🇵🇸</div>
<div class="pal-bar"><div class="pb-r"></div><div class="pb-m"></div><div class="pb-d"></div><div class="pb-w"></div></div>
""", height=220)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    col1, col2 = st.columns(2, gap="small")
    with col1:
        if st.button(T("speaker_btn"), key="btn_spk", use_container_width=True):
            go("speaker_setup")
    with col2:
        if st.button(T("audience_btn"), key="btn_aud", use_container_width=True):
            go("audience_join")

    st.markdown(f"""<div style='text-align:center;font-size:9px;color:#1c1c1c;
  letter-spacing:.07em;padding:10px 0 4px;font-family:monospace;'>
  {esc(T("footer"))} 🇵🇸</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKER SETUP
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker_setup":
    if not st.session_state.room_code:
        code = gen_code(); room_create(code)
        st.session_state.room_code = code
    code = st.session_state.room_code
    rtl  = is_rtl_ui(); ui_dir = "rtl" if rtl else "ltr"

    st.components.v1.html(PALETTE + f"""
<style>
body{{padding:16px 16px 6px;background:transparent;direction:{ui_dir};}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;margin-top:7px;font-family:'Cairo',sans-serif;}}
</style>
<div class="title">{esc(T("your_room"))}</div>
<div class="sub">{esc(T("share_code"))}</div>
""", height=86)

    st.components.v1.html(PALETTE + f"""
<style>
body{{display:flex;flex-direction:column;align-items:center;padding:6px 16px 10px;text-align:center;background:transparent;}}
.lbl{{font-size:10px;color:#333;letter-spacing:.18em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;margin-bottom:10px;}}
.outer{{padding:2px;border-radius:24px;background:linear-gradient(135deg,#ce1126,#000 40%,#007a3d);}}
.box{{background:#060606;border-radius:22px;padding:22px 40px 16px;}}
.code{{font-family:'Bebas Neue',sans-serif;font-size:clamp(88px,24vw,136px);letter-spacing:18px;line-height:1;
  background:linear-gradient(135deg,#ff3348,#ff8a6a,#fff);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.hint{{font-size:11px;color:#2a2a2a;margin-top:7px;font-family:'JetBrains Mono',monospace;}}
</style>
<div class="lbl">{esc(T("room_code_lbl"))}</div>
<div class="outer"><div class="box">
  <div class="code">{esc(code)}</div>
  <div class="hint">{esc(T("code_hint"))}</div>
</div></div>
""", height=212)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2, gap="small")
    with c1:
        if st.button(T("enter_speak"), key="spk_enter", use_container_width=True):
            go("speaker")
    with c2:
        if st.button(T("new_code"), key="spk_newcode", use_container_width=True):
            c = gen_code(); room_create(c)
            st.session_state.room_code = c; st.rerun()
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button(T("back_home"), key="spk_setup_back", use_container_width=True):
        go("home", room_code=None)


# ══════════════════════════════════════════════════════════════════════════════
# AUDIENCE JOIN
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience_join":
    rtl = is_rtl_ui(); ui_dir = "rtl" if rtl else "ltr"

    st.components.v1.html(PALETTE + f"""
<style>
body{{padding:16px 16px 6px;background:transparent;direction:{ui_dir};}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);line-height:.85;letter-spacing:.03em;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;margin-top:7px;font-family:'Cairo',sans-serif;}}
</style>
<div class="title">{esc(T("join_room"))}</div>
<div class="sub">{esc(T("enter_code"))}</div>
""", height=86)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    code_input = st.text_input("ROOM CODE", max_chars=4, placeholder="1234", key="aud_code_field")

    if st.session_state.join_error:
        st.markdown(f"""<div style='background:rgba(206,17,38,.1);border:1px solid rgba(255,51,72,.28);
  border-radius:12px;padding:12px 14px;font-size:13px;color:#ff3348;
  text-align:center;margin:6px 0;font-family:"Cairo",sans-serif;'>❌ {esc(st.session_state.join_error)}</div>""",
                    unsafe_allow_html=True)

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    j1, j2 = st.columns(2, gap="small")
    with j1:
        if st.button(T("join_btn"), key="aud_join_btn", use_container_width=True):
            code = sanitize_code(code_input)
            if len(code) != 4:
                st.session_state.join_error = "Please enter a valid 4-digit code"; st.rerun()
            elif not room_exists(code):
                st.session_state.join_error = f"Room {code} not found — check the code"; st.rerun()
            else:
                st.session_state.join_error = ""
                go("audience", room_code=code)
    with j2:
        if st.button(T("back"), key="aud_join_back", use_container_width=True):
            st.session_state.join_error = ""; go("home")


# ══════════════════════════════════════════════════════════════════════════════
# SPEAKER  — Web Speech API mic, real-time word-by-word
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "speaker":
    if not st.session_state.room_code:
        go("speaker_setup")

    room     = st.session_state.room_code
    rtl      = is_rtl_ui()
    ui_dir   = "rtl" if rtl else "ltr"
    spk_lang = st.session_state.get("spk_lang", "en")

    # ── Header row ────────────────────────────────────────────────────────────
    nl, nr = st.columns([3, 1], gap="small")
    with nl:
        st.components.v1.html(PALETTE + f"""
<style>
body{{padding:16px 16px 4px;background:transparent;direction:{ui_dir};}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);line-height:.85;
  background:linear-gradient(140deg,#f2ede3 30%,#fd6b4b 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;margin-top:6px;font-family:'Cairo',sans-serif;}}
.badge{{display:inline-flex;align-items:center;gap:5px;background:rgba(253,107,75,.1);
  border:1px solid rgba(253,107,75,.25);border-radius:8px;padding:4px 10px;margin-top:7px;
  font-size:11px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;font-weight:700;}}
</style>
<div class="title">{esc(T("speak_now"))}</div>
<div class="sub">{esc(T("tap_mic"))}</div>
<div class="badge">🔑 {esc(T("room"))} {esc(room)}</div>
""", height=112)
    with nr:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(T("home_btn"), key="spk_home", use_container_width=True):
            go("home", room_code=None)

    # ── Language selector ──────────────────────────────────────────────────────
    spk_label = st.selectbox(
        T("speaking_lang"),
        list(SPEAKER_LANGS.keys()),
        index=list(SPEAKER_LANGS.values()).index(spk_lang),
        key="spk_lang_sel",
    )
    st.session_state.spk_lang = SPEAKER_LANGS[spk_label]
    spk_lang = st.session_state.spk_lang

    # ── Controls ──────────────────────────────────────────────────────────────
    sc1, sc2, sc3 = st.columns([2, 2, 2], gap="small")
    with sc2:
        if st.button(T("new_card"), key="new_card_btn", use_container_width=True):
            if st.session_state.card_id:
                card_seal(room, st.session_state.card_id)
            st.session_state.card_id = None; st.rerun()
    with sc3:
        if st.button(T("clear_btn"), key="clr_btn", use_container_width=True):
            db_clear(room); st.session_state.card_id = None; st.rerun()

    # Ensure there's an active card_id the JS can reference
    if not st.session_state.card_id:
        st.session_state.card_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    card_id = st.session_state.card_id

    # ── Web Speech API microphone widget ──────────────────────────────────────
    #
    # This iframe runs entirely in the browser.  It sends interim results
    # word-by-word to our embedded API server at API_PORT.
    #
    spk_lang_bcp47 = {
        "en": "en-US", "ar": "ar-SA", "fr": "fr-FR", "es": "es-ES",
        "de": "de-DE", "tr": "tr-TR", "it": "it-IT", "zh-CN": "zh-CN",
        "ru": "ru-RU", "ja": "ja-JP", "pt": "pt-BR", "ko": "ko-KR",
    }.get(spk_lang, spk_lang)

    unsupported_msg = esc(T("mic_unsupported"))
    denied_msg      = esc(T("mic_denied"))
    start_lbl       = esc(T("mic_start"))
    stop_lbl        = esc(T("mic_stop"))
    recording_lbl   = esc(T("recording"))

    # We put the API base URL in the JS so the iframe can POST to it
    st.components.v1.html(PALETTE + f"""
<style>
body{{
  margin:0;padding:12px 0;background:transparent;
  display:flex;flex-direction:column;align-items:center;gap:10px;
}}
#mic-btn{{
  width:140px;height:140px;border-radius:50%;
  background:#0a0a0a;border:2px solid #1e1e1e;
  display:flex;align-items:center;justify-content:center;
  cursor:pointer;font-size:48px;transition:all .25s;
  -webkit-tap-highlight-color:transparent;user-select:none;
}}
#mic-btn:hover{{border-color:#fd6b4b;box-shadow:0 0 28px rgba(253,107,75,.22);transform:scale(1.04);}}
#mic-btn.recording{{
  border-color:#ce1126;
  box-shadow:0 0 0 8px rgba(206,17,38,.12),0 0 40px rgba(206,17,38,.18);
  animation:pulse-ring 1.4s ease infinite;
}}
@keyframes pulse-ring{{
  0%{{box-shadow:0 0 0 4px rgba(206,17,38,.2),0 0 40px rgba(206,17,38,.1);}}
  50%{{box-shadow:0 0 0 14px rgba(206,17,38,.05),0 0 60px rgba(206,17,38,.22);}}
  100%{{box-shadow:0 0 0 4px rgba(206,17,38,.2),0 0 40px rgba(206,17,38,.1);}}
}}
#status{{
  font-family:'JetBrains Mono',monospace;font-size:11px;color:#555;
  letter-spacing:.08em;text-align:center;min-height:18px;
}}
#status.live{{color:#fd6b4b;}}
#interim{{
  font-family:'Cairo',sans-serif;font-size:15px;font-weight:600;
  color:#888;text-align:center;padding:0 16px;min-height:24px;word-break:break-word;
  max-width:90vw;
}}
</style>

<div id="mic-btn" onclick="toggleMic()">🎤</div>
<div id="status">{start_lbl}</div>
<div id="interim"></div>

<script>
(function(){{
  const API   = 'http://localhost:{API_PORT}';
  const ROOM  = '{esc(room)}';
  const CARD  = '{esc(card_id)}';
  const LANG  = '{esc(spk_lang_bcp47)}';

  const btn     = document.getElementById('mic-btn');
  const status  = document.getElementById('status');
  const interim = document.getElementById('interim');

  let recog = null;
  let running = false;
  let seq = 0;               // monotonically increasing chunk sequence
  let restartTimer = null;

  // Check support
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {{
    status.textContent = '{unsupported_msg}';
    btn.style.opacity = '.4';
    btn.onclick = null;
    return;
  }}

  function buildRecognizer() {{
    const r = new SpeechRecognition();
    r.lang = LANG;
    r.continuous = true;
    r.interimResults = true;
    r.maxAlternatives = 1;

    r.onstart = () => {{
      running = true;
      btn.classList.add('recording');
      btn.textContent = '⏹';
      status.textContent = '{recording_lbl}';
      status.classList.add('live');
    }};

    r.onend = () => {{
      if (running) {{
        // auto-restart (browser stops after ~60 s of silence on mobile)
        restartTimer = setTimeout(() => {{ if (running) r.start(); }}, 300);
      }} else {{
        btn.classList.remove('recording');
        btn.textContent = '🎤';
        status.textContent = '{start_lbl}';
        status.classList.remove('live');
        interim.textContent = '';
      }}
    }};

    r.onerror = (e) => {{
      if (e.error === 'not-allowed' || e.error === 'service-not-allowed') {{
        running = false;
        status.textContent = '{denied_msg}';
        btn.style.opacity = '.5';
      }} else if (e.error === 'network') {{
        // retry silently
        if (running) restartTimer = setTimeout(() => r.start(), 1000);
      }}
      // other errors (aborted, no-speech) — just let onend handle restart
    }};

    r.onresult = (event) => {{
      let interimTxt = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {{
        const res = event.results[i];
        const txt = res[0].transcript.trim();
        if (!txt) continue;
        if (res.isFinal) {{
          seq++;
          sendChunk(txt, false, 'f' + seq);
          interimTxt = '';
        }} else {{
          interimTxt = txt;
          sendChunk(txt, true, 'i' + seq);
        }}
      }}
      interim.textContent = interimTxt;
    }};

    return r;
  }}

  function sendChunk(txt, isInterim, chunkKey) {{
    fetch(API + '/api/chunk', {{
      method: 'POST',
      headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{
        room: ROOM, card_id: CARD,
        chunk_id: CARD + ':' + chunkKey,
        txt: txt, lang: LANG.split('-')[0],
        interim: isInterim
      }})
    }}).catch(() => {{}});  // fire and forget — UDP-style
  }}

  window.toggleMic = function() {{
    if (!running) {{
      recog = buildRecognizer();
      running = true;
      try {{ recog.start(); }} catch(e) {{}}
    }} else {{
      running = false;
      if (restartTimer) clearTimeout(restartTimer);
      try {{ recog.stop(); }} catch(e) {{}}
      // seal the card
      fetch(API + '/api/seal', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{room: ROOM, card_id: CARD}})
      }}).catch(() => {{}});
    }}
  }};
}})();
</script>
""", height=230)

    # ── Live transcript preview (polling SQLite directly — speaker side) ───────
    all_cards = cards_get(room, 6)
    if not all_cards:
        st.components.v1.html(PALETTE + f"""
<style>body{{padding:28px 0;text-align:center;background:transparent;}}</style>
<div style='font-size:38px;margin-bottom:8px;'>🎙️</div>
<div style='font-size:13px;color:#2a2a2a;font-family:"Cairo",sans-serif;'>
  {esc(T("nothing_yet"))}</div>
""", height=90)
    else:
        cards_html = ""
        for i, (cid, chunk_rows, sealed) in enumerate(all_cards):
            # skip pure-interim rows for the speaker preview
            final_rows = [r for r in chunk_rows if not r[3]]  # r[3] = interim flag
            if not final_rows: continue
            full_txt = " ".join(r[0] for r in final_rows if r[0].strip())
            lang  = chunk_rows[0][1] if chunk_rows else ""
            ts    = chunk_rows[-1][2] if chunk_rows else ""
            d     = dir_attr(lang)
            rs    = rtl_style(lang)
            tf    = ("'Noto Naskh Arabic','Cairo',sans-serif" if d == "rtl" else "'Cairo',sans-serif")
            is_live = (i == 0 and not sealed)
            border = "border-left:3px solid #fd6b4b;" if is_live and d == "ltr" else \
                     ("border-right:3px solid #fd6b4b;" if is_live else "")
            bg     = "background:linear-gradient(135deg,rgba(253,107,75,.06),#080808 55%);" if is_live else ""
            badge  = '<span class="ltag live">● LIVE</span>' if is_live else '<span class="ltag done">✓</span>'
            cards_html += f"""
<div class="hc" style="{border}{bg}">
  <div class="meta">
    <span class="ts">🕐 {esc(ts)}</span>
    <span class="ltag lang">{esc((lang or "??").upper())}</span>
    {badge}
    <span class="ts">{len(final_rows)} {esc(T("chunks"))}</span>
  </div>
  <div class="htxt" dir="{d}" style="{rs}font-family:{tf};">{esc(full_txt)}</div>
</div>"""

        st.components.v1.html(PALETTE + f"""
<style>
body{{background:transparent;padding:4px 0 24px;}}
.hc{{background:#070707;border:1px solid #161616;border-radius:14px;padding:14px 16px;margin:5px 0;transition:border-color .2s;}}
.hc:hover{{border-color:#252525;}}
.meta{{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-bottom:7px;}}
.ts{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#2a2a2a;}}
.ltag{{border-radius:5px;padding:1px 8px;font-size:9px;font-weight:700;letter-spacing:.1em;text-transform:uppercase;font-family:'JetBrains Mono',monospace;}}
.ltag.lang{{background:rgba(0,198,94,.08);color:#00c65e;border:1px solid rgba(0,198,94,.2);}}
.ltag.live{{background:rgba(253,107,75,.1);color:#ff8a6a;border:1px solid rgba(253,107,75,.25);}}
.ltag.done{{background:rgba(85,85,85,.1);color:#555;border:1px solid rgba(85,85,85,.2);}}
.htxt{{font-size:15px;font-weight:600;color:#f2ede3;line-height:1.65;}}
</style>
{cards_html}
""", height=min(80 + len(all_cards) * 110, 2200))


# ══════════════════════════════════════════════════════════════════════════════
# AUDIENCE  — polls /api/poll every second, renders word-by-word in JS
# ══════════════════════════════════════════════════════════════════════════════
elif st.session_state.page == "audience":
    if not st.session_state.room_code:
        go("audience_join")

    room   = st.session_state.room_code
    rtl    = is_rtl_ui()
    ui_dir = "rtl" if rtl else "ltr"

    al, ar_ = st.columns([3, 1], gap="small")
    with al:
        st.components.v1.html(PALETTE + f"""
<style>
body{{padding:16px 16px 4px;background:transparent;direction:{ui_dir};}}
.title{{font-family:'Bebas Neue',sans-serif;font-size:clamp(44px,10vw,78px);line-height:.85;
  background:linear-gradient(140deg,#f2ede3 30%,#00c65e 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
.sub{{font-size:10px;color:#3a3a3a;letter-spacing:.12em;text-transform:uppercase;margin-top:6px;font-family:'Cairo',sans-serif;}}
.badge{{display:inline-flex;align-items:center;gap:5px;background:rgba(0,122,61,.1);
  border:1px solid rgba(0,198,94,.25);border-radius:8px;padding:4px 10px;margin-top:7px;
  font-size:11px;color:#00c65e;font-family:'JetBrains Mono',monospace;font-weight:700;}}
</style>
<div class="title">{esc(T("live_subs"))}</div>
<div class="sub">{esc(T("realtime_subs"))}</div>
<div class="badge">🔑 {esc(T("room"))} {esc(room)}</div>
""", height=112)
    with ar_:
        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        if st.button(T("home_btn"), key="aud_home", use_container_width=True):
            go("home", room_code=None)

    # Language + font size
    c1, c2 = st.columns([3, 1], gap="small")
    with c1:
        lc_sel = st.selectbox(
            T("language"),
            list(AUDIENCE_LANGS.keys()),
            index=list(AUDIENCE_LANGS.values()).index(st.session_state.aud_lang),
            label_visibility="collapsed", key="aud_lang_sel",
        )
        st.session_state.aud_lang = AUDIENCE_LANGS[lc_sel]
    with c2:
        if st.button("A−", key="fdn", use_container_width=True):
            st.session_state.aud_fpx = max(16, st.session_state.aud_fpx - 4)
        if st.button("A+", key="fup", use_container_width=True):
            st.session_state.aud_fpx = min(64, st.session_state.aud_fpx + 4)

    tgt     = st.session_state.aud_lang
    fpx     = st.session_state.aud_fpx
    tgt_dir = dir_attr(tgt)
    tgt_sty = rtl_style(tgt)
    tgt_font = ("'Noto Naskh Arabic','Cairo',sans-serif" if tgt_dir == "rtl" else "'Cairo',sans-serif")
    fs_align = "right" if tgt_dir == "rtl" else "left"

    waiting_msg    = esc(T("waiting"))
    will_bcast_msg = esc(T("will_broadcast"))
    live_dot_msg   = esc(T("live_dot"))
    streaming_msg  = esc(T("streaming"))
    waiting_lbl    = esc(T("waiting"))
    previous_lbl   = esc(T("previous"))
    speak_aloud_lbl= esc(T("speak_aloud"))
    copy_lbl       = esc(T("copy_btn"))
    full_lbl        = esc(T("full_btn"))
    tap_close_lbl  = esc(T("tap_close"))
    chunks_lbl     = esc(T("chunks"))

    # Screen-wake lock
    st.components.v1.html("""<script>
(async()=>{if('wakeLock' in navigator){
  try{await navigator.wakeLock.request('screen');}catch(e){}
  document.addEventListener('visibilitychange',async()=>{
    if(document.visibilityState==='visible')
      try{await navigator.wakeLock.request('screen');}catch(e){}
  });
}})();
</script>""", height=1)

    # ── The real-time audience display — pure JS polling ─────────────────────
    st.components.v1.html(PALETTE + f"""
<style>
body{{margin:0;padding:8px 4px 24px;background:transparent;}}

/* ── status bar ── */
#statusbar{{
  display:flex;align-items:center;gap:7px;padding:8px 13px;
  background:#060606;border:1px solid #161616;border-radius:10px;
  font-size:11px;font-family:monospace;margin-bottom:8px;
}}
.dot{{width:7px;height:7px;border-radius:50%;flex-shrink:0;display:inline-block;}}
.dot.live{{background:#00c65e;box-shadow:0 0 0 3px rgba(0,198,94,.15);
  animation:dp 1.2s infinite;}}
.dot.wait{{background:#333;}}
@keyframes dp{{0%,100%{{opacity:1}}50%{{opacity:.15}}}}
#statuslbl{{color:#f2ede3;}}

/* ── live card ── */
#live-wrap{{margin-bottom:6px;}}
.stage{{background:#060606;border-radius:18px;padding:22px 20px 18px;position:relative;overflow:hidden;}}
.glow{{position:absolute;inset:-1px;z-index:0;border-radius:18px;pointer-events:none;
  background:linear-gradient(135deg,rgba(206,17,38,.22),transparent 40%,rgba(0,122,61,.22));}}
.stage::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:3px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);z-index:1;}}
.live-badge{{display:inline-flex;align-items:center;gap:5px;
  background:rgba(253,107,75,.1);border:1px solid rgba(253,107,75,.3);
  border-radius:6px;padding:2px 9px;margin-bottom:10px;
  font-size:10px;color:#ff8a6a;font-family:'JetBrains Mono',monospace;
  font-weight:700;letter-spacing:.08em;position:relative;z-index:2;}}
@keyframes bl{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.bdot{{width:6px;height:6px;border-radius:50%;background:#ff8a6a;animation:bl 1s infinite;display:inline-block;}}
.body{{font-size:{fpx}px;font-weight:700;line-height:1.7;
  font-family:{tgt_font};{tgt_sty}position:relative;z-index:2;word-break:break-word;}}
.body .old{{color:#f2ede3;}}.body .new{{color:#fd6b4b;}}
@keyframes pop{{from{{opacity:.2;transform:translateY(4px)}}to{{opacity:1;transform:none}}}}
.body .new{{animation:pop .25s ease;}}
.meta{{font-family:'JetBrains Mono',monospace;font-size:10px;color:#333;margin-top:10px;position:relative;z-index:2;}}

/* ── action buttons ── */
.row{{display:flex;gap:8px;margin:4px 0 6px;}}
.btn{{flex:1;background:#060606;border:1px solid #161616;border-radius:12px;
  padding:12px 8px;color:#333;font-size:12px;cursor:pointer;
  font-family:'Cairo',sans-serif;font-weight:700;text-align:center;
  -webkit-tap-highlight-color:transparent;transition:all .18s;}}
.btn:active{{background:#161616;color:#f2ede3;transform:scale(.96);}}
.btn:hover{{background:#0a0a0a;color:#f2ede3;border-color:#007a3d;box-shadow:0 3px 12px rgba(0,122,61,.12);}}
#cm{{color:#00c65e;font-size:11px;opacity:0;transition:opacity .3s;align-self:center;}}

/* ── full-screen overlay ── */
#fs{{display:none;position:fixed;inset:0;background:#000;z-index:99999;
  align-items:center;justify-content:center;cursor:pointer;
  flex-direction:column;text-align:{fs_align};padding:32px;}}
#fs-t{{color:#f2ede3;font-weight:700;line-height:1.55;
  font-size:clamp(24px,6vw,60px);max-width:95%;
  direction:{tgt_dir};font-family:{tgt_font};word-break:break-word;}}
#fs-b{{position:absolute;bottom:0;left:0;right:0;height:4px;
  background:linear-gradient(90deg,#ce1126 0%,#ce1126 33%,#000 33%,#000 66%,#007a3d 66%);}}
#fs-h{{position:absolute;bottom:20px;font-size:11px;color:#1a1a1a;font-family:monospace;}}

/* ── waiting state ── */
#waiting{{padding:30px 0;text-align:center;display:none;}}

/* ── previous cards ── */
#prev-label{{margin:10px 0 4px;font-size:10px;color:#444;text-align:center;
  font-family:monospace;letter-spacing:.12em;}}
.pc{{background:#0d0d0d;border:1px solid #1a1a1a;border-radius:14px;
  padding:14px 16px;margin:5px 0;}}
.at{{font-size:15px;font-weight:600;color:#888;line-height:1.7;word-break:break-word;}}
.ats{{font-size:10px;color:#333;font-family:'JetBrains Mono',monospace;margin-top:6px;}}
</style>

<!-- Status bar -->
<div id="statusbar">
  <span class="dot wait" id="dot"></span>
  <span id="statuslbl">{waiting_lbl}</span>
</div>

<!-- Live card -->
<div id="live-wrap" style="display:none;">
  <div class="stage">
    <div class="glow"></div>
    <div class="live-badge"><span class="bdot"></span> <span id="badge-txt">LIVE · 0 {chunks_lbl}</span></div>
    <div class="body" dir="{tgt_dir}" id="body-txt">
      <span class="old" id="old-txt"></span><span class="new" id="new-txt"></span>
    </div>
    <div class="meta" id="meta-txt"></div>
  </div>
  <div class="row">
    <button class="btn" onclick="speakIt()">{speak_aloud_lbl}</button>
    <button class="btn" onclick="copyIt()">{copy_lbl}</button>
    <button class="btn" onclick="openFs()">{full_lbl}</button>
    <span id="cm">✓</span>
  </div>
</div>

<!-- Waiting placeholder -->
<div id="waiting">
  <div style="font-size:42px;margin-bottom:9px">⏳</div>
  <div style="font-size:14px;color:#888;font-family:'Cairo',sans-serif;">{waiting_msg}</div>
  <div style="font-size:11px;color:#555;margin-top:5px;font-family:'Cairo',sans-serif;">{will_bcast_msg}</div>
</div>

<!-- Previous sealed cards -->
<div id="prev-label" style="display:none;">{previous_lbl}</div>
<div id="prev-cards"></div>

<!-- Full-screen overlay -->
<div id="fs" onclick="closeFs()">
  <div id="fs-t" dir="{tgt_dir}"></div>
  <div id="fs-h">{tap_close_lbl}</div>
  <div id="fs-b"></div>
</div>

<script>
(function(){{
  const API   = 'http://localhost:{API_PORT}';
  const ROOM  = '{esc(room)}';
  const TGT   = '{esc(tgt)}';
  const CHUNKS_LBL = '{chunks_lbl}';

  const dot      = document.getElementById('dot');
  const statusLbl= document.getElementById('statuslbl');
  const liveWrap = document.getElementById('live-wrap');
  const waiting  = document.getElementById('waiting');
  const badgeTxt = document.getElementById('badge-txt');
  const oldTxt   = document.getElementById('old-txt');
  const newTxt   = document.getElementById('new-txt');
  const metaTxt  = document.getElementById('meta-txt');
  const fsEl     = document.getElementById('fs');
  const fsTxt    = document.getElementById('fs-t');
  const prevLabel= document.getElementById('prev-label');
  const prevCards= document.getElementById('prev-cards');

  let sinceId = 0;
  // Per-card accumulation: cardId → {{texts: [...], lang, ts, sealed}}
  const cards = {{}};
  let liveCardId = null;

  function getCardTexts(cid) {{
    return (cards[cid]?.texts || []).join(' ');
  }}

  function renderLive() {{
    if (!liveCardId || !cards[liveCardId]) {{
      liveWrap.style.display = 'none';
      waiting.style.display  = 'block';
      dot.className = 'dot wait';
      statusLbl.textContent = '{waiting_lbl}';
      return;
    }}
    waiting.style.display  = 'none';
    liveWrap.style.display = 'block';
    dot.className = 'dot live';
    statusLbl.textContent = '🔴 {live_dot_msg} · {streaming_msg}';

    const txts  = cards[liveCardId].texts;
    const lang  = cards[liveCardId].lang || '';
    const ts    = cards[liveCardId].ts   || '';
    const n     = txts.length;
    const full  = txts.join(' ');

    if (n > 1) {{
      oldTxt.textContent = txts.slice(0, -1).join(' ') + ' ';
    }} else {{
      oldTxt.textContent = '';
    }}
    // Force re-trigger animation on new text
    newTxt.style.animation = 'none';
    newTxt.offsetHeight;  // reflow
    newTxt.style.animation = '';
    newTxt.textContent = txts[n-1] || '';

    badgeTxt.textContent = 'LIVE · ' + n + ' ' + CHUNKS_LBL;
    metaTxt.textContent = '🕐 ' + ts + ' · ' + (lang.toUpperCase() || 'AUTO') + ' → ' + TGT.toUpperCase();
    fsTxt.textContent = full;
  }}

  function renderPrevious() {{
    const sealed = Object.entries(cards)
      .filter(([cid,v]) => v.sealed && cid !== liveCardId)
      .sort((a,b) => b[1].maxId - a[1].maxId);

    if (sealed.length === 0) {{
      prevLabel.style.display = 'none';
      prevCards.innerHTML = '';
      return;
    }}
    prevLabel.style.display = 'block';
    prevCards.innerHTML = sealed.map(([cid,v]) => {{
      const full = v.texts.join(' ');
      const d = ('{tgt_dir}');
      const rs = d==='rtl' ? 'direction:rtl;text-align:right;unicode-bidi:embed;' : 'direction:ltr;text-align:left;';
      const tf = d==='rtl' ? "'Noto Naskh Arabic','Cairo',sans-serif" : "'Cairo',sans-serif";
      return `<div class="pc">
        <div class="at" dir="${{d}}" style="${{rs}}font-family:${{tf}};">${{full}}</div>
        <div class="ats">🕐 ${{v.ts}} · ${{(v.lang||'').toUpperCase()}} → {esc(tgt.upper())} · ${{v.texts.length}} {chunks_lbl}</div>
      </div>`;
    }}).join('');
  }}

  async function poll() {{
    try {{
      const res  = await fetch(`${{API}}/api/poll?room=${{ROOM}}&since=${{sinceId}}&tgt=${{TGT}}`);
      const data = await res.json();
      if (!data.chunks || data.chunks.length === 0) {{ return; }}

      for (const ch of data.chunks) {{
        if (ch.id > sinceId) sinceId = ch.id;
        const cid = ch.card_id;
        const txt = ch.translated || ch.txt;

        if (!cards[cid]) cards[cid] = {{texts:[], lang:ch.lang, ts:ch.ts, sealed:false, maxId:0}};
        const card = cards[cid];
        card.ts = ch.ts;
        if (ch.id > card.maxId) card.maxId = ch.id;

        if (ch.interim) {{
          // Replace the last slot if it's interim, else push
          if (card._lastInterim) {{
            card.texts[card.texts.length-1] = txt;
          }} else {{
            card.texts.push(txt);
            card._lastInterim = true;
          }}
        }} else {{
          // Final: replace interim slot or push new
          if (card._lastInterim && card.texts.length > 0) {{
            card.texts[card.texts.length-1] = txt;
          }} else {{
            card.texts.push(txt);
          }}
          card._lastInterim = false;
        }}

        if (ch.sealed) {{
          card.sealed = true;
          if (liveCardId === cid) liveCardId = null;
        }} else {{
          liveCardId = cid;
        }}
      }}

      renderLive();
      renderPrevious();
    }} catch(e) {{
      // network hiccup — skip silently
    }}
  }}

  // Start polling every 1 second
  setInterval(poll, 1000);
  poll();  // immediate first call

  // ── Utility buttons ──────────────────────────────────────────────────────
  window.speakIt = function() {{
    const txt = liveCardId ? getCardTexts(liveCardId) : '';
    if (!txt) return;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(txt);
    u.lang = TGT; speechSynthesis.speak(u);
  }};
  window.copyIt = function() {{
    const txt = liveCardId ? getCardTexts(liveCardId) : '';
    if (!txt) return;
    navigator.clipboard.writeText(txt).then(()=>{{
      const m=document.getElementById('cm'); m.style.opacity='1';
      setTimeout(()=>m.style.opacity='0',2000);
    }}).catch(()=>{{}});
    if(navigator.vibrate) navigator.vibrate(40);
  }};
  window.openFs  = function() {{ fsEl.style.display='flex'; }};
  window.closeFs = function() {{ fsEl.style.display='none'; }};

}})();
</script>
""", height=700)
