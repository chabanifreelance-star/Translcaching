"""Shared database helpers and CSS for LiveTranslate."""

import sqlite3
import os
import tempfile
from datetime import datetime

DB_PATH = os.path.join(tempfile.gettempdir(), "livetranslate_v3.db")

# ── Palestine-inspired palette ────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Cairo:wght@400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
  --black:    #0a0a0a;
  --surface:  #141414;
  --card:     #1c1c1c;
  --border:   #282828;
  --white:    #f0ede6;
  --muted:    #5a5a54;
  --green:    #007a3d;
  --green-lt: #00c65e;
  --red:      #ce1126;
  --red-lt:   #ff3348;
  --amber:    #f59e0b;
}

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
  font-family: 'Cairo', sans-serif !important;
  background: var(--black) !important;
  color: var(--white) !important;
}

.stApp { background: var(--black) !important; }

/* hide hamburger / header */
#MainMenu, header, footer { visibility: hidden !important; }

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-track { background: var(--black); }
::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }

/* ── Flag stripe ── */
.flag {
  display: flex; height: 5px; width: 100%;
  border-radius: 3px; overflow: hidden; margin: 0 0 32px;
}
.f-bk { flex:1; background:#2a2a2a; }
.f-wh { flex:1; background:#3a3a3a; }
.f-gr { flex:1; background:var(--green); }
.f-rd { flex:1; background:var(--red); }

/* ── Buttons ── */
.stButton > button {
  font-family: 'Cairo', sans-serif !important;
  font-weight: 700 !important;
  border: none !important;
  border-radius: 10px !important;
  transition: all .2s !important;
  letter-spacing: .04em !important;
}

/* ── Cards ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 26px;
  margin: 10px 0;
}
.card.live {
  border-left: 3px solid var(--green-lt);
  background: linear-gradient(135deg, rgba(0,198,94,.06), var(--card) 60%);
  animation: fadein .4s ease;
}
@keyframes fadein {
  from { opacity:.3; transform:translateY(-8px); }
  to   { opacity:1;  transform:translateY(0); }
}

/* ── Dot indicators ── */
.dot {
  display:inline-block; width:10px; height:10px;
  border-radius:50%; margin-right:8px; flex-shrink:0;
}
.dot-idle    { background:#333; }
.dot-rec     { background:var(--red-lt);   box-shadow:0 0 0 5px rgba(206,17,38,.18); animation:pulse 1.1s infinite; }
.dot-proc    { background:var(--amber);    box-shadow:0 0 0 5px rgba(245,158,11,.18); animation:pulse .55s infinite; }
.dot-live    { background:var(--green-lt); box-shadow:0 0 0 5px rgba(0,198,94,.18);  animation:pulse 1.4s infinite; }
@keyframes pulse {
  0%,100%{ opacity:1; transform:scale(1); }
  50%    { opacity:.3; transform:scale(.75); }
}

/* ── Status bar ── */
.sbar {
  display:flex; align-items:center; gap:12px;
  padding:13px 20px;
  background:var(--surface); border:1px solid var(--border); border-radius:10px;
  font-size:13px; font-family:'JetBrains Mono',monospace;
  margin:12px 0;
}

/* ── Lang tag ── */
.ltag {
  display:inline-block;
  background:rgba(0,198,94,.08); color:var(--green-lt);
  border:1px solid rgba(0,198,94,.2); border-radius:4px;
  padding:2px 9px; font-size:10px; font-weight:700;
  letter-spacing:.1em; text-transform:uppercase;
  font-family:'JetBrains Mono',monospace;
}
.ltag-red { background:rgba(206,17,38,.08)!important; color:var(--red-lt)!important; border-color:rgba(206,17,38,.2)!important; }

/* ── Silence bar ── */
.sil-wrap { background:#222; border-radius:4px; height:5px; margin:8px 0; overflow:hidden; }
.sil-fill { height:100%; border-radius:4px; transition:width .3s linear; }

/* ── Select / Toggle ── */
.stSelectbox > div > div {
  background:var(--surface) !important;
  border:1px solid var(--border) !important;
  color:var(--white) !important; border-radius:10px !important;
}
.stSelectbox label, .stToggle label, .stSlider label {
  color:var(--white) !important; font-weight:600 !important;
}
hr { border-color:var(--border) !important; }
[data-testid="stAudioInput"] {
  background: var(--surface) !important;
  border: 1px dashed var(--border) !important;
  border-radius: 14px !important;
}
</style>
"""

FLAG = """
<div class="flag">
  <div class="f-bk"></div><div class="f-wh"></div>
  <div class="f-gr"></div><div class="f-rd"></div>
</div>
"""

# ── DB helpers ────────────────────────────────────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS segments (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                text  TEXT    NOT NULL,
                lang  TEXT    NOT NULL DEFAULT '',
                ts    TEXT    NOT NULL
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                val TEXT NOT NULL DEFAULT ''
            )
        """)
        c.execute("INSERT OR IGNORE INTO meta(key,val) VALUES('spk_state','idle')")
        c.commit()

def save_segment(text: str, lang: str):
    with sqlite3.connect(DB_PATH) as c:
        c.execute(
            "INSERT INTO segments(text,lang,ts) VALUES(?,?,?)",
            (text.strip(), lang, datetime.now().strftime("%H:%M:%S")),
        )
        c.commit()

def get_latest(limit: int = 5):
    with sqlite3.connect(DB_PATH) as c:
        rows = c.execute(
            "SELECT text, lang, ts FROM segments ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return list(reversed(rows))

def get_count() -> int:
    with sqlite3.connect(DB_PATH) as c:
        return c.execute("SELECT COUNT(*) FROM segments").fetchone()[0]

def clear_all():
    with sqlite3.connect(DB_PATH) as c:
        c.execute("DELETE FROM segments")
        c.commit()

def set_state(val: str):
    with sqlite3.connect(DB_PATH) as c:
        c.execute("UPDATE meta SET val=? WHERE key='spk_state'", (val,))
        c.commit()

def get_state() -> str:
    with sqlite3.connect(DB_PATH) as c:
        r = c.execute("SELECT val FROM meta WHERE key='spk_state'").fetchone()
    return r[0] if r else "idle"

init_db()
