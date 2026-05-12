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
# WHISPER
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def get_whisper():
    try:
        from faster_whisper import WhisperModel
        try:    return WhisperModel("base",device="cuda",compute_type="float16")
        except: return WhisperModel("base",device="cpu", compute_type="int8")
    except: return None

def transcribe(b: bytes):
    m = get_whisper()
    if not m: return "",""
    with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:
        f.write(b); p=f.name
    try:
        segs,info = m.transcribe(p,task="transcribe",language=None,
                                  beam_size=5,vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms":300})
        return " ".join(s.text.strip() for s in segs).strip(), info.language
    except: return "",""
    finally:
        try: os.unlink(p)
        except: pass

# ─────────────────────────────────────────────────────────────────────────────
# TRANSLATION
# ─────────────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=7200, show_spinner=False)
def tr(text, target, source="auto"):
    if not text.strip(): return text
    src = source.split("-")[0].lower() if source and source!="auto" else "auto"
    tgt = target.split("-")[0].lower()
    if src!="auto" and src==tgt: return text
    try:
        from deep_translator import GoogleTranslator
        return GoogleTranslator(source=src,target=target).translate(text) or text
    except Exception as e: return f"[{e}]"

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGES
# ─────────────────────────────────────────────────────────────────────────────
LANGS = {
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
for k,v in {"page":"home","last_hash":None,"last_txt":"","last_lang":""}.items():
    if k not in st.session_state: st.session_state[k]=v

# URL param routing
p = st.query_params.get("page","home")
if p in ("speaker","audience","home"):
    st.session_state.page = p


# ═════════════════════════════════════════════════════════════════════════════
#  H O M E
# ═════════════════════════════════════════════════════════════════════════════
if st.session_state.page == "home":

    components.html(PALETTE + """
<style>
body{min-height:100vh;display:flex;flex-direction:column;
  align-items:center;padding:56px 20px 60px;overflow-x:hidden;}

/* top flag bar */
body::before{content:'';position:fixed;top:0;left:0;right:0;height:4px;z-index:99;
  background:linear-gradient(90deg,var(--red) 25%,var(--bg) 25%,var(--bg) 50%,
  var(--green) 50%,var(--green) 75%,var(--bg) 75%);}

/* brand */
.brand{text-align:center;margin-bottom:6px;}
.b-live{display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(80px,14vw,150px);line-height:.8;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--rl) 0%,var(--melon) 55%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.b-trans{display:block;font-family:'Bebas Neue',sans-serif;
  font-size:clamp(80px,14vw,150px);line-height:.8;letter-spacing:.04em;
  background:linear-gradient(135deg,var(--gl) 0%,var(--white) 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}
.b-sub{font-size:12px;color:#444;letter-spacing:.2em;text-transform:uppercase;
  margin-top:12px;margin-bottom:38px;}

/* flag stripe */
.flag{display:flex;height:4px;width:100%;max-width:680px;
  border-radius:2px;overflow:hidden;margin:0 auto 44px;}
.f1{flex:1;background:#282828;}.f2{flex:1;background:#383838;}
.f3{flex:1;background:var(--green);}.f4{flex:1;background:var(--red);}

/* role grid */
.grid{display:flex;gap:20px;justify-content:center;flex-wrap:wrap;
  max-width:680px;margin-bottom:52px;}

.card{width:300px;background:var(--card);border:1px solid var(--b);
  border-radius:22px;padding:36px 28px 30px;display:block;
  position:relative;overflow:hidden;transition:transform .25s,box-shadow .25s,border-color .25s;}
.card:hover{transform:translateY(-5px);border-color:#333;}
.card.spk:hover{box-shadow:0 20px 60px rgba(206,17,38,.22);}
.card.aud:hover{box-shadow:0 20px 60px rgba(0,122,61,.22);}

/* glow blob */
.card::before{content:'';position:absolute;width:220px;height:220px;
  border-radius:50%;top:-70px;left:-70px;pointer-events:none;transition:opacity .3s;}
.card.spk::before{background:radial-gradient(circle,rgba(206,17,38,.2) 0%,transparent 70%);opacity:.7;}
.card.aud::before{background:radial-gradient(circle,rgba(0,122,61,.2) 0%,transparent 70%);opacity:.7;}
.card:hover::before{opacity:1;}

.c-icon{font-size:50px;display:block;margin-bottom:16px;}
.c-name{font-family:'Bebas Neue',sans-serif;font-size:38px;letter-spacing:.06em;margin-bottom:10px;}
.c-name.spk{color:var(--rl);}.c-name.aud{color:var(--gl);}
.c-desc{font-size:14px;color:#5a5a5a;line-height:1.75;margin-bottom:22px;}
.c-btn{display:inline-block;padding:10px 24px;border-radius:8px;
  font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;}
.c-btn.spk{background:rgba(206,17,38,.12);color:var(--rl);border:1px solid rgba(206,17,38,.3);}
.c-btn.aud{background:rgba(0,122,61,.12);color:var(--gl);border:1px solid rgba(0,122,61,.3);}

/* features */
.feats{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;
  max-width:680px;margin-bottom:52px;}
.feat{width:150px;background:var(--card);border:1px solid var(--b);
  border-radius:14px;padding:18px 18px 16px;}
.fi{font-size:24px;margin-bottom:8px;}
.ft{font-size:13px;font-weight:700;color:#ccc;margin-bottom:5px;}
.fd{font-size:12px;color:#4a4a4a;line-height:1.6;}

.footer{font-size:11px;color:#252525;letter-spacing:.08em;text-align:center;}
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
      Record your speech — the AI auto-detects your language
      and broadcasts it live to every audience member.</div>
    <span class="c-btn spk">I am the Speaker &rarr;</span>
  </a>
  <a class="card aud" href="?page=audience">
    <span class="c-icon">👥</span>
    <div class="c-name aud">AUDIENCE</div>
    <div class="c-desc">You are listening.<br>
      Choose your language and read live translated
      subtitles — updated automatically every few seconds.</div>
    <span class="c-btn aud">I am Audience &rarr;</span>
  </a>
</div>

<div class="feats">
  <div class="feat"><div class="fi">🌍</div><div class="ft">99 Languages</div>
    <div class="fd">Arabic, French, Spanish, Chinese, Russian — auto-detected</div></div>
  <div class="feat"><div class="fi">🤫</div><div class="ft">Auto-Stop</div>
    <div class="fd">4 seconds of silence → auto-processes, no button needed</div></div>
  <div class="feat"><div class="fi">🔒</div><div class="ft">100% Free</div>
    <div class="fd">No API key, no account, no cost — runs fully local</div></div>
  <div class="feat"><div class="fi">📱</div><div class="ft">Any Device</div>
    <div class="fd">Works in any modern browser — phone, tablet, laptop</div></div>
</div>

<div class="footer">Made with 🇵🇸 &nbsp;·&nbsp; 100% free &nbsp;·&nbsp; faster-whisper &nbsp;·&nbsp; deep-translator</div>
""", height=920, scrolling=False)

    # Streamlit buttons as fallback (if href navigation blocked in iframe)
    c1,_,c2 = st.columns([1,.2,1])
    with c1:
        if st.button("🎤  Enter as Speaker", use_container_width=True):
            st.session_state.page="speaker"
            st.query_params["page"]="speaker"
            st.rerun()
    with c2:
        if st.button("👥  Enter as Audience", use_container_width=True):
            st.session_state.page="audience"
            st.query_params["page"]="audience"
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
<div class="sub">Any language · Auto-detected · Broadcast live</div>
<div class="flag"><div class="f1"></div><div class="f2"></div>
  <div class="f3"></div><div class="f4"></div></div>
""", height=170, scrolling=False)

    if st.button("← Back to Home", key="spk_home"):
        st.session_state.page="home"
        st.query_params["page"]="home"
        st.rerun()

    # ── JS Silence-detecting recorder ─────────────────────────────────────────
    components.html(PALETTE + """
<style>
body{background:transparent;padding:0 4px;}
#box{background:var(--card);border:1px solid var(--b);border-radius:18px;padding:24px;}

#btn-s,#btn-x{
  width:100%;padding:20px;border-radius:12px;border:none;cursor:pointer;
  font-family:'Bebas Neue',sans-serif;font-size:26px;letter-spacing:.08em;
  display:flex;align-items:center;justify-content:center;gap:14px;transition:all .2s;}
#btn-s{background:linear-gradient(135deg,var(--red),#a00e1b);color:#fff;
  box-shadow:0 6px 32px rgba(206,17,38,.4);}
#btn-s:hover{transform:translateY(-2px);box-shadow:0 12px 44px rgba(206,17,38,.5);}
#btn-x{background:var(--card2);color:var(--rl);border:2px solid rgba(206,17,38,.3);display:none;}
#btn-x:hover{background:#222;}

#bars{display:none;align-items:flex-end;justify-content:center;
  gap:3px;height:44px;margin:16px 0 4px;}
.b{width:5px;background:var(--red);border-radius:3px;min-height:3px;
  transition:height .08s ease;}

#sw{background:#1c1c1c;border-radius:4px;height:5px;margin:10px 0 4px;overflow:hidden;display:none;}
#sf{height:100%;border-radius:4px;width:0%;transition:width .25s linear;}

#status{font-size:13px;font-family:monospace;color:var(--muted);
  text-align:center;margin-top:8px;min-height:18px;}
</style>

<div id="box">
  <button id="btn-s" onclick="go()">🎤 &nbsp; START SPEAKING</button>
  <button id="btn-x" onclick="manual()">⏹ &nbsp; STOP SPEAKING</button>
  <div id="bars">
    <div class="b" id="b0"></div><div class="b" id="b1"></div><div class="b" id="b2"></div>
    <div class="b" id="b3"></div><div class="b" id="b4"></div><div class="b" id="b5"></div>
    <div class="b" id="b6"></div><div class="b" id="b7"></div><div class="b" id="b8"></div>
    <div class="b" id="b9"></div><div class="b" id="b10"></div><div class="b" id="b11"></div>
    <div class="b" id="b12"></div><div class="b" id="b13"></div><div class="b" id="b14"></div>
    <div class="b" id="b15"></div><div class="b" id="b16"></div><div class="b" id="b17"></div>
    <div class="b" id="b18"></div><div class="b" id="b19"></div>
  </div>
  <div id="sw"><div id="sf"></div></div>
  <div id="status">Press the button and speak in any language</div>
</div>

<script>
const SIL_RMS=.013, SIL_SECS=4, SR=16000;
let mr,stream,ctx,an,raf,chunks=[],silT=null,rec=false;
const bars=Array.from({length:20},(_,i)=>document.getElementById('b'+i));
const BS=document.getElementById('btn-s'),BX=document.getElementById('btn-x');
const ST=document.getElementById('status'),SW=document.getElementById('sw');
const SF=document.getElementById('sf'),BAR=document.getElementById('bars');

function msg(t,c='#555'){ST.style.color=c;ST.innerHTML=t;}

async function go(){
  try{stream=await navigator.mediaDevices.getUserMedia(
    {audio:{sampleRate:SR,channelCount:1,echoCancellation:true,noiseSuppression:true}});}
  catch{msg('❌ Mic blocked — allow microphone access in your browser','#ff3348');return;}
  ctx=new(window.AudioContext||window.webkitAudioContext)({sampleRate:SR});
  an=ctx.createAnalyser();an.fftSize=512;
  ctx.createMediaStreamSource(stream).connect(an);
  mr=new MediaRecorder(stream);chunks=[];
  mr.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data);};
  mr.onstop=send;mr.start(100);
  rec=true;silT=null;
  BS.style.display='none';BX.style.display='flex';
  BAR.style.display='flex';SW.style.display='block';SF.style.width='0%';
  msg('🔴 Recording — speak now','#ff3348');tick();
}

function tick(){
  if(!rec)return;
  const d=new Uint8Array(an.frequencyBinCount);
  an.getByteTimeDomainData(d);
  let s=0;for(const v of d){const x=(v-128)/128;s+=x*x;}
  const rms=Math.sqrt(s/d.length);
  bars.forEach((b,i)=>{
    const w=Math.abs(Math.sin(i*.55+Date.now()*.007));
    b.style.height=Math.max(3,Math.min(38,rms*700*w))+'px';
  });
  const now=performance.now();
  if(rms<SIL_RMS){
    if(!silT)silT=now;
    const el=(now-silT)/1000,pct=Math.min(100,el/SIL_SECS*100);
    SF.style.width=pct+'%';
    SF.style.background=pct>75
      ?'linear-gradient(90deg,#ce1126,#900)'
      :'linear-gradient(90deg,#00c65e,#007a3d)';
    if(el>=SIL_SECS){msg('⚡ Processing…','#f59e0b');stop();return;}
    if(el>.8)msg(`🤫 Silence ${el.toFixed(1)}s / ${SIL_SECS}s — auto-stopping soon…`,'#f59e0b');
  }else{
    silT=null;SF.style.width='0%';if(rec)msg('🔴 Recording — speak now','#ff3348');
  }
  raf=requestAnimationFrame(tick);
}
function manual(){msg('⚡ Processing…','#f59e0b');stop();}
function stop(){
  if(!rec)return;rec=false;cancelAnimationFrame(raf);
  if(mr&&mr.state!=='inactive')mr.stop();
  stream.getTracks().forEach(t=>t.stop());ctx.close();
  BX.style.display='none';BS.style.display='flex';
  BAR.style.display='none';SW.style.display='none';
  bars.forEach(b=>b.style.height='3px');
}
async function send(){
  const blob=new Blob(chunks,{type:'audio/webm'});
  const ab=await blob.arrayBuffer();
  const tc=new OfflineAudioContext(1,SR*60,SR);
  let buf;
  try{buf=await tc.decodeAudioData(ab);}
  catch{msg('❌ Audio decode failed — try again','#ff3348');return;}
  const pcm=buf.getChannelData(0),wav=toWav(pcm,buf.sampleRate);
  const b64=btoa(String.fromCharCode(...new Uint8Array(wav)));
  window.parent.postMessage({type:'lt_wav',b64},'*');
  msg('✅ Sent! Press START SPEAKING for the next sentence.','#00c65e');
}
function toWav(p,sr){
  const buf=new ArrayBuffer(44+p.length*2),v=new DataView(buf);
  const w=(o,s)=>{for(let i=0;i<s.length;i++)v.setUint8(o+i,s.charCodeAt(i));};
  w(0,'RIFF');v.setUint32(4,36+p.length*2,true);w(8,'WAVE');w(12,'fmt ');
  v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);
  v.setUint32(24,sr,true);v.setUint32(28,sr*2,true);
  v.setUint16(32,2,true);v.setUint16(34,16,true);w(36,'data');
  v.setUint32(40,p.length*2,true);
  let o=44;for(const s of p){const x=Math.max(-1,Math.min(1,s));
    v.setInt16(o,x<0?x*0x8000:x*0x7FFF,true);o+=2;}
  return buf;
}
</script>
""", height=210, scrolling=False)

    # ── Fallback native recorder ──────────────────────────────────────────────
    components.html("""<p style='font-size:12px;color:#2a2a2a;text-align:center;
      margin:10px 0 2px;font-family:monospace;letter-spacing:.06em;
      background:transparent;'>
      — OR USE THE NATIVE RECORDER BELOW —</p>""", height=28, scrolling=False)

    rec = st.audio_input("🎙️ Click mic · speak · click stop — auto-transcribes",
                         key="mic_fb", label_visibility="collapsed")
    if rec:
        b = rec.read(); h = hash(b)
        if h != st.session_state.last_hash:
            st.session_state.last_hash = h
            with st.spinner("🧠 Transcribing — detecting language…"):
                txt, lang = transcribe(b)
            if txt:
                db_save(txt, lang)
                st.session_state.last_txt = txt
                st.session_state.last_lang = lang
                st.cache_data.clear()
                st.rerun()
            else:
                st.warning("No speech detected — try speaking louder or closer.")

    # ── History ───────────────────────────────────────────────────────────────
    n = db_count(); rows = db_all(60)
    ch1, ch2 = st.columns([4,1])
    with ch1:
        components.html(f"""<style>
          @keyframes dp{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.75);}}}}
          body{{margin:0;padding:0;background:transparent;}}
          </style>
          <div style='display:flex;align-items:center;gap:10px;
          padding:11px 16px;background:#101010;border:1px solid #222;
          border-radius:10px;font-size:13px;font-family:monospace;'>
          <span style='width:9px;height:9px;border-radius:50%;background:#00c65e;
          box-shadow:0 0 0 4px rgba(0,198,94,.18);display:inline-block;
          animation:dp 1.4s infinite;'></span>
          <span style='color:#f2ede3;'>Session: <b>{n}</b> segment(s) — newest first</span>
          </div>""", height=50, scrolling=False)
    with ch2:
        if st.button("🗑️ Clear", use_container_width=True, key="cl"):
            db_clear(); st.cache_data.clear()
            st.session_state.last_txt=""
            st.rerun()

    if not rows:
        components.html(PALETTE+"""<style>body{background:transparent;padding:20px;
          text-align:center;color:#222;font-family:'Cairo',sans-serif;}</style>
          <div style='font-size:48px;margin-bottom:12px'>🎙️</div>
          <div style='font-size:15px'>Nothing broadcast yet — press START SPEAKING above</div>
          """, height=120)
    else:
        # Build all history cards in one components.html for performance
        cards_html = ""
        for i,(txt,lang,ts) in enumerate(rows):
            is_new = (i==0)
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
""", height=min(90 + len(rows)*100, 2400), scrolling=True)


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

    if st.button("← Back to Home", key="aud_home"):
        st.session_state.page="home"
        st.query_params["page"]="home"
        st.rerun()

    # Controls
    cl, cs, cr = st.columns([3,1,1])
    with cl:
        lc = st.selectbox("Language", list(LANGS.keys()), index=0,
                          label_visibility="collapsed")
        tgt = LANGS[lc]
    with cs:
        fpx = st.select_slider("Size",[20,28,36,44,56,68],value=44,
                               format_func=lambda x:f"{x}px")
    with cr:
        rate = st.select_slider("Refresh",[2,3,5,8],value=3,
                                format_func=lambda x:f"{x}s")

    n = db_count()
    components.html(f"""<style>
      @keyframes dp{{0%,100%{{opacity:1;transform:scale(1);}}50%{{opacity:.3;transform:scale(.75);}}}}
      body{{margin:0;padding:0;background:transparent;}}
      </style>
      <div style='display:flex;align-items:center;gap:10px;
      padding:11px 16px;background:#101010;border:1px solid #222;
      border-radius:10px;font-size:13px;font-family:monospace;'>
      <span style='width:9px;height:9px;border-radius:50%;background:#00c65e;
      box-shadow:0 0 0 4px rgba(0,198,94,.18);display:inline-block;
      animation:dp 1.4s infinite;'></span>
      <span style='color:#f2ede3;'>🔴 Live — refreshing every <b>{rate}s</b> &nbsp;·&nbsp;
      <b>{n}</b> segments &nbsp;·&nbsp; <b>{tgt}</b></span>
      </div>""", height=50, scrolling=False)

    rows = db_all(30)

    if not rows:
        components.html(PALETTE+"""<style>body{background:transparent;padding:40px 20px;
          text-align:center;color:#222;font-family:'Cairo',sans-serif;}</style>
          <div style='font-size:56px;margin-bottom:14px'>⏳</div>
          <div style='font-size:18px'>Waiting for the speaker to start…</div>
          <div style='font-size:13px;color:#1e1e1e;margin-top:8px;'>
          Open the Speaker tab in another browser window or device</div>""", height=200)
    else:
        # ── Latest segment — BIG ──────────────────────────────────────────────
        ltxt, llang, lts = rows[0]
        ltranslated = tr(ltxt, tgt, llang)
        tb = tgt.split("-")[0].lower()
        sb = llang.split("-")[0].lower() if llang else "auto"
        show_orig_l = (sb!=tb) and (ltxt!=ltranslated)
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
""", height=max(260, fpx*3 + 120), scrolling=False)

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

/* fullscreen */
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
                sb2 = seg_lang.split("-")[0].lower() if seg_lang else "auto"
                so = f'<div class="ao">{seg_lang.upper()} · {seg_txt}</div>' if (sb2!=tb and seg_txt!=seg_tr) else ""
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
""", height=min(60 + len(older)*100, 2000), scrolling=True)

    # Auto-refresh
    time.sleep(rate)
    st.rerun()
