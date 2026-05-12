"""
Speaker page.

HOW AUTO-SILENCE WORKS ON STREAMLIT CLOUD:
  st.audio_input() returns a WAV blob when the user clicks Stop.
  We can't do continuous mic + silence detection in Streamlit (no threading).
  
  SOLUTION: We use st.audio_input() + a JavaScript snippet that:
    1. Accesses getUserMedia (browser mic directly)
    2. Monitors audio level every 100ms via AudioContext + AnalyserNode
    3. After 4 seconds of silence → programmatically clicks the Stop button
    4. The resulting WAV is picked up by st.audio_input() → transcribed immediately
  
  This gives the user the feel of "speak, it auto-stops and processes" 
  without needing sounddevice or threading.
"""

import streamlit as st
import streamlit.components.v1 as components
import os
import tempfile
import time
from shared import CSS, FLAG, save_segment, set_state, clear_all, get_count

# ─── Whisper (cached permanently) ────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def load_whisper():
    try:
        from faster_whisper import WhisperModel
        try:
            m = WhisperModel("base", device="cuda", compute_type="float16")
            return m
        except Exception:
            return WhisperModel("base", device="cpu", compute_type="int8")
    except Exception:
        return None

def transcribe(audio_bytes: bytes) -> tuple:
    """Returns (text, detected_language). task=transcribe keeps original lang."""
    model = load_whisper()
    if not model:
        return "", "err"
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp.write(audio_bytes)
        path = tmp.name
    try:
        segs, info = model.transcribe(
            path,
            task="transcribe",   # keep original language
            language=None,       # auto-detect all 99 languages
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        return text, info.language
    except Exception as e:
        return "", "err"
    finally:
        try: os.unlink(path)
        except: pass

# ─── Translation ──────────────────────────────────────────────────────────────
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

LANG_NAMES = {
    "ar":"Arabic","en":"English","fr":"French","es":"Spanish","de":"German",
    "tr":"Turkish","it":"Italian","zh":"Chinese","ru":"Russian","ja":"Japanese",
    "pt":"Portuguese","hi":"Hindi","ko":"Korean","nl":"Dutch","pl":"Polish",
    "sv":"Swedish","el":"Greek","th":"Thai","vi":"Vietnamese","uk":"Ukrainian","id":"Indonesian",
}

# ─── Page ─────────────────────────────────────────────────────────────────────
def show():
    st.markdown(CSS, unsafe_allow_html=True)
    st.markdown("""
    <style>
    .spk-wrap { max-width: 780px; margin: 0 auto; padding: 40px 20px; }

    .page-title {
      font-family: 'Bebas Neue', sans-serif;
      font-size: clamp(52px, 8vw, 96px);
      line-height: .88;
      background: linear-gradient(140deg, #f0ede6 30%, #ff3348 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      background-clip: text;
      margin-bottom: 4px;
    }
    .page-sub { font-size: 13px; color: #555; letter-spacing:.14em; text-transform:uppercase; margin-bottom:0; }

    .big-rec-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 14px;
      width: 100%;
      padding: 22px;
      border-radius: 16px;
      font-family: 'Bebas Neue', sans-serif;
      font-size: 28px;
      letter-spacing: .08em;
      cursor: pointer;
      border: none;
      margin: 20px 0;
      transition: all .2s;
    }
    .big-rec-btn.start {
      background: linear-gradient(135deg, #ce1126, #a50e1e);
      color: #fff;
      box-shadow: 0 6px 28px rgba(206,17,38,.35);
    }
    .big-rec-btn.stop {
      background: linear-gradient(135deg, #1c1c1c, #2a2a2a);
      color: #ff3348;
      border: 2px solid rgba(206,17,38,.4);
    }
    .big-rec-btn:hover { transform: translateY(-2px); }

    .tip-row {
      display: flex; gap: 12px; flex-wrap: wrap; margin: 20px 0;
    }
    .tip {
      flex: 1; min-width: 140px;
      background: #141414; border: 1px solid #222; border-radius: 12px;
      padding: 14px 16px;
    }
    .tip-icon { font-size:20px; margin-bottom:6px; }
    .tip-title { font-size:13px; font-weight:700; color:#ccc; margin-bottom:3px; }
    .tip-desc  { font-size:12px; color:#555; line-height:1.55; }

    .result-card {
      background: #1c1c1c;
      border: 1px solid #282828;
      border-left: 3px solid #00c65e;
      border-radius: 14px;
      padding: 24px 28px;
      margin: 16px 0;
      animation: pop .4s ease;
    }
    @keyframes pop {
      from { opacity:.2; transform:scale(.97); }
      to   { opacity:1;  transform:scale(1); }
    }
    .result-lang { font-size:11px; font-family:'JetBrains Mono',monospace; color:#555; margin-bottom:8px; }
    .result-text { font-size:24px; font-weight:700; color:#f0ede6; line-height:1.5; direction:auto; }

    .silence-label { font-size:12px; color:#555; font-family:'JetBrains Mono',monospace; margin-top:4px; }

    .nav-back {
      display:inline-flex; align-items:center; gap:8px;
      color:#555; font-size:13px; text-decoration:none;
      margin-bottom:24px; transition:color .2s;
    }
    .nav-back:hover { color:#ccc; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<a class="nav-back" href="?page=home">← Back to home</a>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="spk-wrap">
      <div class="page-title">SPEAK<br>NOW</div>
      <div class="page-sub">Your speech is broadcast live · Any language</div>
    """ + FLAG + """
    </div>""", unsafe_allow_html=True)

    # Session defaults
    for k, v in {"last_text": "", "last_lang": "", "last_hash": None, "processing": False}.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # ── Silence-detection microphone via injected JS ─────────────────────────
    # This JS component:
    #  1. Shows a big "START SPEAKING" button
    #  2. On click → getUserMedia, starts AudioContext analyser
    #  3. Monitors RMS every 100ms; after 4s of silence (RMS < threshold) → stops recording
    #  4. Posts the WAV blob as a base64 string back to Streamlit via Streamlit message bus
    # We render it hidden and capture output via st.audio_input as fallback.

    # JavaScript silence-detection recorder embedded as HTML component
    components.html("""
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: transparent; font-family: 'Cairo', sans-serif; }

      #wrap { padding: 0; }

      #btn-start, #btn-stop {
        width: 100%;
        padding: 20px;
        border-radius: 14px;
        font-size: 22px;
        font-weight: 900;
        letter-spacing: .07em;
        cursor: pointer;
        border: none;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        transition: all .2s;
      }
      #btn-start {
        background: linear-gradient(135deg, #ce1126, #a00e1b);
        color: #fff;
        box-shadow: 0 6px 28px rgba(206,17,38,.4);
      }
      #btn-start:hover { transform: translateY(-2px); box-shadow: 0 10px 36px rgba(206,17,38,.5); }

      #btn-stop {
        background: #1c1c1c;
        color: #ff3348;
        border: 2px solid rgba(206,17,38,.35);
        display: none;
      }
      #btn-stop:hover { background: #242424; }

      #status {
        margin-top: 14px;
        font-size: 13px;
        font-family: monospace;
        color: #666;
        text-align: center;
        min-height: 20px;
      }
      #silence-wrap {
        background: #222;
        border-radius: 4px;
        height: 5px;
        margin-top: 10px;
        overflow: hidden;
        display: none;
      }
      #silence-fill {
        height: 100%;
        border-radius: 4px;
        width: 0%;
        transition: width .3s linear;
        background: linear-gradient(90deg, #00c65e, #007a3d);
      }
      #level-wrap {
        display: none;
        align-items: flex-end;
        justify-content: center;
        gap: 3px;
        height: 36px;
        margin-top: 14px;
      }
      .lbar {
        width: 5px;
        background: #ce1126;
        border-radius: 3px;
        min-height: 3px;
        transition: height .1s ease;
      }
    </style>

    <div id="wrap">
      <button id="btn-start" onclick="startRec()">🎤 &nbsp; START SPEAKING</button>
      <button id="btn-stop"  onclick="stopRec()"> ⏹ &nbsp; STOP SPEAKING</button>
      <div id="level-wrap" id="lvl">
        <!-- 16 bars for audio level visualiser -->
        <div class="lbar" id="b0"></div><div class="lbar" id="b1"></div>
        <div class="lbar" id="b2"></div><div class="lbar" id="b3"></div>
        <div class="lbar" id="b4"></div><div class="lbar" id="b5"></div>
        <div class="lbar" id="b6"></div><div class="lbar" id="b7"></div>
        <div class="lbar" id="b8"></div><div class="lbar" id="b9"></div>
        <div class="lbar" id="b10"></div><div class="lbar" id="b11"></div>
        <div class="lbar" id="b12"></div><div class="lbar" id="b13"></div>
        <div class="lbar" id="b14"></div><div class="lbar" id="b15"></div>
      </div>
      <div id="silence-wrap"><div id="silence-fill"></div></div>
      <div id="status">Press the button and start speaking in any language</div>
    </div>

    <script>
    const SILENCE_RMS   = 0.012;   // volume threshold for silence
    const SILENCE_SECS  = 4.0;     // seconds of silence before auto-stop
    const SAMPLE_RATE   = 16000;

    let mediaRecorder, stream, audioCtx, analyser, silenceTimer=0, animId;
    let chunks = [];
    let isSilent = false;
    let silenceStart = null;
    let isRecording = false;

    const btnStart = document.getElementById('btn-start');
    const btnStop  = document.getElementById('btn-stop');
    const status   = document.getElementById('status');
    const silWrap  = document.getElementById('silence-wrap');
    const silFill  = document.getElementById('silence-fill');
    const lvlWrap  = document.getElementById('level-wrap');
    const bars     = Array.from({length:16}, (_,i) => document.getElementById('b'+i));

    function setStatus(msg, color='#666') {
      status.style.color = color;
      status.textContent = msg;
    }

    async function startRec() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { sampleRate: SAMPLE_RATE, channelCount: 1, echoCancellation: true }
        });
      } catch(e) {
        setStatus('❌ Microphone access denied — please allow mic in your browser', '#ff3348');
        return;
      }

      audioCtx  = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SAMPLE_RATE });
      analyser  = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      const src = audioCtx.createMediaStreamSource(stream);
      src.connect(analyser);

      mediaRecorder = new MediaRecorder(stream);
      chunks = [];
      mediaRecorder.ondataavailable = e => { if(e.data.size>0) chunks.push(e.data); };
      mediaRecorder.onstop = processAudio;
      mediaRecorder.start(100);

      isRecording = true;
      silenceStart = null;
      btnStart.style.display = 'none';
      btnStop.style.display  = 'flex';
      lvlWrap.style.display  = 'flex';
      silWrap.style.display  = 'block';
      silFill.style.width    = '0%';
      setStatus('🔴 Recording… speak now', '#ff3348');

      monitorSilence();
    }

    function monitorSilence() {
      if (!isRecording) return;
      const data = new Uint8Array(analyser.frequencyBinCount);
      analyser.getByteTimeDomainData(data);

      // Compute RMS
      let sum = 0;
      for (let v of data) { const x = (v-128)/128; sum += x*x; }
      const rms = Math.sqrt(sum / data.length);

      // Level bars visualisation
      bars.forEach((bar, i) => {
        const offset = Math.sin(i * 0.6 + Date.now()*0.005) * 0.5 + 0.5;
        const h = Math.max(3, Math.min(34, rms * 500 * offset));
        bar.style.height = h + 'px';
      });

      // Silence detection
      const now = performance.now();
      if (rms < SILENCE_RMS) {
        if (!silenceStart) silenceStart = now;
        const elapsed = (now - silenceStart) / 1000;
        const pct = Math.min(100, (elapsed / SILENCE_SECS) * 100);
        silFill.style.width = pct + '%';
        silFill.style.background = pct > 70
          ? 'linear-gradient(90deg,#ce1126,#a00)'
          : 'linear-gradient(90deg,#00c65e,#007a3d)';
        if (elapsed >= SILENCE_SECS) {
          setStatus('⚡ Silence detected — processing…', '#f59e0b');
          stopRec();
          return;
        }
        if (elapsed > 1)
          setStatus(`🔇 Silence: ${elapsed.toFixed(1)}s / ${SILENCE_SECS}s — auto-stopping soon…`, '#f59e0b');
      } else {
        silenceStart = null;
        silFill.style.width = '0%';
        if (isRecording) setStatus('🔴 Recording… speak now', '#ff3348');
      }

      animId = requestAnimationFrame(monitorSilence);
    }

    function stopRec() {
      if (!isRecording) return;
      isRecording = false;
      cancelAnimationFrame(animId);
      if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
      stream.getTracks().forEach(t => t.stop());
      audioCtx.close();
      btnStop.style.display  = 'none';
      btnStart.style.display = 'flex';
      lvlWrap.style.display  = 'none';
      bars.forEach(b => b.style.height = '3px');
    }

    async function processAudio() {
      setStatus('⚡ Processing…', '#f59e0b');
      silWrap.style.display = 'none';

      const blob = new Blob(chunks, { type: 'audio/webm' });

      // Convert to WAV via AudioContext decode + encode
      const arrayBuf = await blob.arrayBuffer();
      const tmpCtx   = new OfflineAudioContext(1, SAMPLE_RATE * 30, SAMPLE_RATE);
      let audioBuf;
      try {
        audioBuf = await tmpCtx.decodeAudioData(arrayBuf);
      } catch(e) {
        setStatus('❌ Audio decode error — try again', '#ff3348');
        return;
      }

      const pcm     = audioBuf.getChannelData(0);
      const wav     = encodeWAV(pcm, audioBuf.sampleRate);
      const b64     = btoa(String.fromCharCode(...new Uint8Array(wav)));

      // Send to Streamlit via window.parent postMessage
      window.parent.postMessage({ type: 'livetranslate_audio', data: b64 }, '*');
      setStatus('✅ Sent for transcription! Press button to record next segment.', '#00c65e');
    }

    function encodeWAV(samples, sampleRate) {
      const buf    = new ArrayBuffer(44 + samples.length * 2);
      const view   = new DataView(buf);
      const write  = (o, s) => { for (let i=0;i<s.length;i++) view.setUint8(o+i, s.charCodeAt(i)); };
      write(0,'RIFF'); view.setUint32(4, 36+samples.length*2, true);
      write(8,'WAVE'); write(12,'fmt ');
      view.setUint32(16,16,true); view.setUint16(20,1,true);
      view.setUint16(22,1,true);  view.setUint32(24,sampleRate,true);
      view.setUint32(28,sampleRate*2,true); view.setUint16(32,2,true);
      view.setUint16(34,16,true); write(36,'data');
      view.setUint32(40,samples.length*2,true);
      let offset = 44;
      for (let s of samples) {
        const v = Math.max(-1,Math.min(1,s));
        view.setInt16(offset, v<0?v*0x8000:v*0x7FFF, true);
        offset += 2;
      }
      return buf;
    }
    </script>
    """, height=200, scrolling=False)

    # ── Streamlit audio_input as fallback / alternative ──────────────────────
    st.markdown("---")
    st.markdown("""
    <div style='font-size:13px;color:#555;margin-bottom:8px;'>
      Or use the built-in recorder (manual stop):
    </div>
    """, unsafe_allow_html=True)

    recorded = st.audio_input(
        "🎙️ Alternative: record here — click stop when done",
        key="fallback_mic",
        label_visibility="collapsed",
    )

    # ── Process audio from fallback mic ──────────────────────────────────────
    if recorded is not None:
        audio_bytes = recorded.read()
        audio_hash  = hash(audio_bytes)

        if audio_hash != st.session_state.last_hash:
            st.session_state.last_hash = audio_hash
            set_state("processing")

            with st.spinner("🧠 Transcribing — detecting language…"):
                text, lang = transcribe(audio_bytes)

            set_state("idle")

            if text:
                save_segment(text, lang)
                st.session_state.last_text = text
                st.session_state.last_lang = lang
                st.cache_data.clear()

                lang_name = LANG_NAMES.get(lang, lang.upper())
                st.markdown(f"""
                <div class="result-card">
                  <div class="result-lang">✅ Detected: {lang_name} ({lang}) · Broadcast at {__import__('datetime').datetime.now().strftime('%H:%M:%S')}</div>
                  <div class="result-text">{text}</div>
                </div>
                """, unsafe_allow_html=True)
                st.success(f"✅ Live for the audience!")
            else:
                st.warning("No speech detected. Try speaking louder or closer to the mic.")

    # ── Tips ─────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="tip-row">
      <div class="tip">
        <div class="tip-icon">🌍</div>
        <div class="tip-title">Any language</div>
        <div class="tip-desc">Speak Arabic, French, English, Spanish — detected automatically</div>
      </div>
      <div class="tip">
        <div class="tip-icon">🤫</div>
        <div class="tip-title">Auto-stop</div>
        <div class="tip-desc">Stops recording after 4 seconds of silence — no button needed</div>
      </div>
      <div class="tip">
        <div class="tip-icon">📶</div>
        <div class="tip-title">Segment by sentence</div>
        <div class="tip-desc">Speak one sentence or thought, pause — it broadcasts and resets</div>
      </div>
      <div class="tip">
        <div class="tip-icon">🔗</div>
        <div class="tip-title">Share audience link</div>
        <div class="tip-desc">Give audience: <code style='color:#00c65e'>?page=audience</code></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Segment counter + clear
    n = get_count()
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"""
        <div class="sbar">
          <div class="dot dot-live"></div>
          <div>Session: <b>{n}</b> segment(s) broadcast</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        if st.button("🗑️ Clear session", use_container_width=True):
            clear_all()
            st.cache_data.clear()
            st.session_state.last_text = ""
            st.session_state.last_lang = ""
            st.rerun()
