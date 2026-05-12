"""Home page — choose Speaker or Audience."""
import streamlit as st
from shared import CSS, FLAG


def show():
    st.markdown(CSS, unsafe_allow_html=True)

    st.markdown("""
    <style>
    .home-wrap {
      max-width: 720px;
      margin: 0 auto;
      padding: 60px 20px 40px;
      text-align: center;
    }
    .brand {
      font-family: 'Bebas Neue', sans-serif;
      font-size: clamp(64px, 10vw, 110px);
      line-height: .88;
      background: linear-gradient(140deg, #f0ede6 20%, #00c65e 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      background-clip: text;
      letter-spacing: .03em;
      margin-bottom: 6px;
    }
    .brand-sub {
      font-size: 13px;
      color: #555;
      letter-spacing: .16em;
      text-transform: uppercase;
      margin-bottom: 40px;
    }

    .role-grid { display:flex; gap:18px; justify-content:center; flex-wrap:wrap; margin-top:16px; }

    .role-card {
      width: 280px;
      background: #141414;
      border: 1px solid #242424;
      border-radius: 18px;
      padding: 36px 28px;
      cursor: pointer;
      text-decoration: none;
      display: block;
      transition: all .25s;
      position: relative;
      overflow: hidden;
    }
    .role-card::before {
      content:'';
      position:absolute; inset:0;
      opacity:0; transition:opacity .25s;
    }
    .role-card.spk::before { background: radial-gradient(circle at top left, rgba(206,17,38,.12), transparent 70%); }
    .role-card.aud::before { background: radial-gradient(circle at top left, rgba(0,122,61,.12), transparent 70%); }
    .role-card:hover { transform:translateY(-4px); border-color:#444; }
    .role-card:hover::before { opacity:1; }

    .role-icon { font-size: 52px; margin-bottom: 16px; }
    .role-name {
      font-family: 'Bebas Neue', sans-serif;
      font-size: 32px;
      letter-spacing: .06em;
      margin-bottom: 10px;
    }
    .role-name.spk { color: #ff3348; }
    .role-name.aud { color: #00c65e; }
    .role-desc { font-size: 14px; color: #666; line-height: 1.65; }

    .role-btn {
      display: inline-block;
      margin-top: 20px;
      padding: 10px 28px;
      border-radius: 8px;
      font-weight: 700;
      font-size: 13px;
      letter-spacing: .08em;
      text-transform: uppercase;
      text-decoration: none;
    }
    .role-btn.spk { background: rgba(206,17,38,.15); color:#ff3348; border:1px solid rgba(206,17,38,.3); }
    .role-btn.aud { background: rgba(0,122,61,.15);  color:#00c65e; border:1px solid rgba(0,122,61,.3); }

    .features {
      margin-top: 60px;
      display: flex;
      gap: 14px;
      justify-content: center;
      flex-wrap: wrap;
      text-align: left;
    }
    .feat {
      background: #141414;
      border: 1px solid #222;
      border-radius: 12px;
      padding: 18px 20px;
      width: 190px;
    }
    .feat-icon { font-size: 24px; margin-bottom: 8px; }
    .feat-title { font-size: 14px; font-weight: 700; color: #ddd; margin-bottom: 4px; }
    .feat-desc  { font-size: 12px; color: #555; line-height: 1.6; }

    .footer {
      margin-top: 56px;
      font-size: 12px;
      color: #333;
      letter-spacing: .06em;
    }
    </style>

    <div class="home-wrap">
      <div class="brand">LIVE<br>TRANSLATE</div>
      <div class="brand-sub">Real-time multilingual conference subtitles · 🇵🇸</div>
    """ + FLAG + """
      <div class="role-grid">

        <a class="role-card spk" href="?page=speaker">
          <div class="role-icon">🎤</div>
          <div class="role-name spk">SPEAKER</div>
          <div class="role-desc">
            You are presenting.<br>
            Record your speech — the AI auto-detects your language
            and broadcasts it live to the audience.
          </div>
          <span class="role-btn spk">I am the Speaker →</span>
        </a>

        <a class="role-card aud" href="?page=audience">
          <div class="role-icon">👥</div>
          <div class="role-name aud">AUDIENCE</div>
          <div class="role-desc">
            You are listening.<br>
            Choose your language and read the live translated
            subtitles in real time.
          </div>
          <span class="role-btn aud">I am Audience →</span>
        </a>

      </div>

      <div class="features">
        <div class="feat">
          <div class="feat-icon">🌍</div>
          <div class="feat-title">99 Languages</div>
          <div class="feat-desc">Arabic, French, Spanish, Chinese, Russian and more — auto-detected</div>
        </div>
        <div class="feat">
          <div class="feat-icon">⚡</div>
          <div class="feat-title">Instant</div>
          <div class="feat-desc">Silence detection — auto-processes after 4 seconds of quiet</div>
        </div>
        <div class="feat">
          <div class="feat-icon">🔒</div>
          <div class="feat-title">100% Free</div>
          <div class="feat-desc">No API key, no account, no cost — runs fully local</div>
        </div>
        <div class="feat">
          <div class="feat-icon">📱</div>
          <div class="feat-title">Any Device</div>
          <div class="feat-desc">Works in any browser — phone, tablet, laptop</div>
        </div>
      </div>

      <div class="footer">Made with 🇵🇸 — 100% free · faster-whisper · deep-translator</div>
    </div>
    """, unsafe_allow_html=True)
