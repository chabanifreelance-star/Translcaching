"""
Audience page — live translated subtitles.
Polls the DB every few seconds and shows only the latest segment large and clear.
Extra features: font size control, text-to-speech, copy button.
"""

import streamlit as st
import time
from shared import CSS, FLAG, get_latest, get_count, get_state

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

@st.cache_data(ttl=7200, show_spinner=False)
def translate(text: str, target: str, source: str = "auto") -> str:
    if not text: return text
    src = source.split("-")[0].lower() if source and source != "auto" else "auto"
    tgt = target.split("-")[0].lower()
    if src != "auto" and src == tgt: return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src, target=target).translate(text) or text
    except Exception as e:
        return f"[Translation error: {e}]"


def show():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("""
    <style>
    .aud-wrap { max-width: 860px; margin: 0 auto; padding: 40px 20px; }

    .page-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: clamp(52px, 8vw, 96px);
      line-height: .88;
      background: linear-gradient(140deg, #f0ede6 30%, #00c65e 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 4px;
    }
    .page-sub { font-size: 13px; color: #555; letter-spacing:.14em; text-transform:uppercase; }

    /* Big subtitle display */
    .sub-stage {
      background: #0f0f0f;
      border: 1px solid #222;
      border-radius: 20px;
      padding: 40px 36px;
      margin: 24px 0;
      min-height: 200px;
      display: flex;
      flex-direction: column;
      justify-content: center;
      position: relative;
      overflow: hidden;
    }
    .sub-stage::before {
      content:'';
      position:absolute;
      bottom:0;left:0;right:0;
      height:3px;
      background: linear-gradient(90deg, #ce1126 0%, #1a1a1a 30%, #007a3d 100%);
    }
    .sub-original {
      font-size: 14px;
      color: #444;
      font-style: italic;
      margin-bottom: 16px;
      direction: auto;
      line-height: 1.6;
    }
    .sub-translated {
      color: #f0ede6;
      font-weight: 700;
      line-height: 1.5;
      direction: auto;
      animation: fadein .5s ease;
      word-break: break-word;
    }
    @keyframes fadein {
      from { opacity:.2; transform:translateY(10px); }
      to   { opacity:1;  transform:translateY(0); }
    }
    .sub-ts {
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px;
      color: #333;
      margin-top: 18px;
    }
    .sub-empty {
      text-align: center;
      color: #2a2a2a;
      font-size: 18px;
      padding: 40px 0;
    }
    .sub-empty .big { font-size: 56px; margin-bottom: 12px; }

    /* Controls row */
    .ctrl-row {
      display: flex;
      gap: 14px;
      align-items: center;
      flex-wrap: wrap;
      margin: 14px 0;
    }
    .ctrl-btn {
      background: #1c1c1c;
      border: 1px solid #282828;
      border-radius: 8px;
      padding: 8px 16px;
      color: #aaa;
      font-size: 13px;
      cursor: pointer;
      transition: all .2s;
      font-family: 'Cairo', sans-serif;
    }
    .ctrl-btn:hover { background: #242424; color: #fff; border-color: #444; }

    .nav-back {
      display:inline-flex; align-items:center; gap:8px;
      color:#555; font-size:13px; text-decoration:none;
      margin-bottom:24px; transition:color .2s;
    }
    .nav-back:hover { color:#ccc; }

    /* Font size controls embedded in JS */
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<a class="nav-back" href="?page=home">← Back to home</a>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="aud-wrap">
      <div class="page-title">LIVE<br>SUBTITLES</div>
      <div class="page-sub">Choose your language — translation appears instantly</div>
    """ + FLAG + """
    </div>""", unsafe_allow_html=True)

    # ── Language + settings ───────────────────────────────────────────────────
    col_lang, col_size, col_refresh = st.columns([3, 1, 1])
    with col_lang:
        lang_choice = st.selectbox(
            "🌐 My language:",
            list(LANGUAGES.keys()),
            index=0,
            label_visibility="collapsed",
        )
        target = LANGUAGES[lang_choice]

    with col_size:
        font_size = st.select_slider(
            "Text size",
            options=[20, 26, 32, 40, 52, 64],
            value=40,
            format_func=lambda x: f"{x}px",
            label_visibility="visible",
        )

    with col_refresh:
        rate = st.select_slider(
            "Refresh",
            options=[2, 3, 5, 8],
            value=3,
            format_func=lambda x: f"{x}s",
            label_visibility="visible",
        )

    # ── Status ────────────────────────────────────────────────────────────────
    spk_state = get_state()
    n = get_count()
    dot_cls = "dot-live" if spk_state in ("listening", "processing") else "dot-idle"
    spk_msg  = "🔴 Speaker is live" if spk_state in ("listening", "processing") else f"Speaker offline · {n} segments received"

    st.markdown(f"""
    <div class="sbar">
      <div class="dot {dot_cls}"></div>
      <div>{spk_msg} &nbsp;·&nbsp; Refreshing every <b>{rate}s</b></div>
    </div>
    """, unsafe_allow_html=True)

    # ── Subtitle stage ────────────────────────────────────────────────────────
    segs = get_latest(1)   # only the LATEST segment

    if not segs:
        st.markdown(f"""
        <div class="sub-stage">
          <div class="sub-empty">
            <div class="big">⏳</div>
            Waiting for the speaker to start…
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        text, lang, ts = segs[0]
        translated = translate(text, target, lang)

        tgt_base = target.split("-")[0].lower()
        src_base = lang.split("-")[0].lower() if lang else "auto"
        show_orig = (src_base != tgt_base) and (text != translated)

        orig_html = ""
        if show_orig:
            orig_html = f'<div class="sub-original">{lang.upper()} · {text}</div>'

        st.markdown(f"""
        <div class="sub-stage">
          {orig_html}
          <div class="sub-translated" style="font-size:{font_size}px">{translated}</div>
          <div class="sub-ts">🕐 {ts} &nbsp;·&nbsp; {lang.upper()} → {target.upper()}</div>
        </div>
        """, unsafe_allow_html=True)

        # ── Extra audience features ───────────────────────────────────────────
        import streamlit.components.v1 as components
        components.html(f"""
        <style>
          body {{ background:transparent; margin:0; font-family:Cairo,sans-serif; }}
          .row {{ display:flex; gap:10px; flex-wrap:wrap; }}
          .btn {{
            background:#1c1c1c; border:1px solid #282828; border-radius:8px;
            padding:9px 18px; color:#aaa; font-size:13px; cursor:pointer;
            transition:all .2s; font-family:Cairo,sans-serif;
          }}
          .btn:hover {{ background:#242424; color:#fff; border-color:#555; }}
          .btn:active {{ transform:scale(.97); }}
          #copy-msg {{ color:#00c65e; font-size:12px; margin-left:8px; opacity:0; transition:opacity .3s; }}
        </style>
        <div class="row">
          <button class="btn" onclick="speakText()">🔊 Read aloud</button>
          <button class="btn" onclick="copyText()">📋 Copy</button>
          <button class="btn" onclick="toggleFullscreen()">⛶ Fullscreen subtitle</button>
          <span id="copy-msg">Copied!</span>
        </div>

        <div id="fs-overlay" style="
          display:none;
          position:fixed;inset:0;
          background:#000;
          z-index:9999;
          align-items:center;justify-content:center;
          text-align:center;
          padding:40px;
          cursor:pointer;
        " onclick="toggleFullscreen()">
          <div style="
            color:#f0ede6;
            font-size:clamp(36px,6vw,80px);
            font-weight:700;
            direction:auto;
            line-height:1.4;
            max-width:90%;
          ">{translated}</div>
          <div style="position:absolute;bottom:24px;left:0;right:0;
            font-size:13px;color:#333;font-family:monospace;">
            Click anywhere to close · {lang.upper()} → {target.upper()}
          </div>
          <div style="position:absolute;bottom:0;left:0;right:0;height:4px;
            background:linear-gradient(90deg,#ce1126 0%,#111 30%,#007a3d 100%);"></div>
        </div>

        <script>
        const TRANSLATED = {repr(translated)};
        const LANG_CODE  = "{target[:2]}";

        function speakText() {{
          if (!window.speechSynthesis) {{ alert("Text-to-speech not supported in this browser"); return; }}
          const utt = new SpeechSynthesisUtterance(TRANSLATED);
          utt.lang = "{target}";
          window.speechSynthesis.cancel();
          window.speechSynthesis.speak(utt);
        }}

        function copyText() {{
          navigator.clipboard.writeText(TRANSLATED).then(() => {{
            const msg = document.getElementById('copy-msg');
            msg.style.opacity = '1';
            setTimeout(() => msg.style.opacity='0', 2000);
          }});
        }}

        function toggleFullscreen() {{
          const ov = document.getElementById('fs-overlay');
          ov.style.display = ov.style.display === 'flex' ? 'none' : 'flex';
        }}
        </script>
        """, height=60, scrolling=False)

    # ── Previous segments (last 4, smaller) ──────────────────────────────────
    prev_segs = get_latest(5)[:-1]  # skip the latest (already shown big)
    if prev_segs:
        st.markdown("""
        <div style='margin-top:24px;margin-bottom:8px;font-size:12px;color:#333;
          font-family:JetBrains Mono,monospace;letter-spacing:.08em;'>
          PREVIOUS SEGMENTS
        </div>
        """, unsafe_allow_html=True)
        for seg_text, seg_lang, seg_ts in reversed(prev_segs):
            seg_translated = translate(seg_text, target, seg_lang)
            tgt_base = target.split("-")[0].lower()
            src_base = seg_lang.split("-")[0].lower() if seg_lang else "auto"
            show_orig_prev = (src_base != tgt_base) and (seg_text != seg_translated)
            orig_prev = f'<div style="font-size:12px;color:#333;font-style:italic;margin-bottom:6px;direction:auto">{seg_lang.upper()} · {seg_text}</div>' if show_orig_prev else ""
            st.markdown(f"""
            <div class="card" style="padding:14px 20px;margin:6px 0;opacity:.6;">
              {orig_prev}
              <div style="font-size:16px;font-weight:600;direction:auto;color:#bbb;">{seg_translated}</div>
              <div style="font-size:11px;color:#333;margin-top:6px;font-family:JetBrains Mono,monospace">🕐 {seg_ts}</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    time.sleep(rate)
    st.rerun()
