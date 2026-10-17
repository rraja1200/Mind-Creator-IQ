import os
import json
import asyncio
import sqlite3
import datetime
import time
from io import BytesIO
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import edge_tts

try:
    from moviepy.editor import ImageClip, VideoFileClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy import ImageClip, VideoFileClip, AudioFileClip, concatenate_videoclips

from google import genai

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

st.set_page_config(page_title="YouTube IQ - AI Video Studio", layout="wide")

def init_db():
    conn = sqlite3.connect("youtube_iq.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT,
                    niche TEXT,
                    sub_niche TEXT,
                    video_style TEXT,
                    topic TEXT,
                    script TEXT,
                    seo_data TEXT,
                    thumbnail_path TEXT,
                    video_path TEXT,
                    status TEXT,
                    created_at TEXT
                )''')
    conn.commit()
    conn.close()

init_db()

MODES = {
    "1. USA High-RPM Wealth & Finance ($40-60 RPM)": {"lang": "American English", "voice": "en-US-ChristopherNeural", "audience": "US High Intent"},
    "2. Geo & Map Mysteries Shorts": {"lang": "American English", "voice": "en-US-JennyNeural", "audience": "Global Geo Viewers"}
}

HIGH_RPM_NICHES = {
    "Personal Finance & Wealth": ["Buy Borrow Die Strategy", "Tax Loopholes of the Rich", "Real Estate Syndication"],
    "Geography & Map Mysteries": ["Why Countries Border Like This", "Secret Enclaves & Islands", "Invisible World Borders"]
}

VOICE_OPTIONS = {
    "US Male (Christopher - Real Documentary)": "en-US-ChristopherNeural",
    "US Female (Jenny - Pro Narrator)": "en-US-JennyNeural"
}

def generate_ai_content(prompt):
    if not GEMINI_API_KEY:
        st.error("⚠️ Gemini API Key missing! Check Streamlit Secrets.")
        return None
    client = genai.Client(api_key=GEMINI_API_KEY)
    models_pool = ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-pro"]
    
    for attempt in range(3):
        for model_name in models_pool:
            try:
                res = client.models.generate_content(model=model_name, contents=prompt)
                if res and res.text:
                    return res.text
            except Exception:
                continue
        time.sleep(1)
    st.error("⚠️ Server busy. Retrying...")
    return None

async def _save_tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)

# Connected AI Visual & Stock Video Frame Generator (No Black Screen)
def generate_connected_ai_frame(vis_prompt, sub_text, format_type, path, scene_idx=0):
    w, h = (1080, 1920) if format_type == "Shorts (9:16)" else (1920, 1080)
    
    # Try fetching a real high-quality dynamic background image based on prompt
    img = None
    try:
        encoded_q = requests.utils.quote(f"{vis_prompt}, cinematic satellite map, 4k, hyperrealistic")
        url = f"https://image.pollinations.ai/prompt/{encoded_q}?width={w}&height={h}&nologo=true"
        res = requests.get(url, timeout=25)
        if res.status_code == 200:
            img = Image.open(BytesIO(res.content)).convert("RGB").resize((w, h))
    except Exception:
        pass

    # Fallback professional animated background if network lags
    if img is None:
        img = Image.new("RGB", (w, h), color=(10, 22, 40))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(60, 60), (w - 60, h - 60)], outline=(56, 189, 248), width=3)
        draw.text((100, 120), f"AI SATELLITE FEED // SCENE 0{scene_idx + 1}", fill=(56, 189, 248))
        draw.text((100, 200), vis_prompt[:120], fill=(255, 255, 255))

    # Clean Pro Subtitle Banner at Bottom
    if sub_text:
        draw = ImageDraw.Draw(img)
        bar_top = int(h * 0.76)
        draw.rectangle([(0, bar_top), (w, h)], fill=(0, 0, 0))
        draw.rectangle([(0, bar_top), (w, bar_top + 10)], fill=(234, 179, 8))
        
        wrapped_sub = sub_text[:85] + ("..." if len(sub_text) > 85 else "")
        draw.text((70, bar_top + 45), wrapped_sub, fill=(255, 255, 255))
        
    img.save(path, "JPEG", quality=95)
    return path

def build_connected_ai_video(scenes, voice_id, format_type):
    os.makedirs("outputs/ai_render", exist_ok=True)
    w, h = (1080, 1920) if format_type == "Shorts (9:16)" else (1920, 1080)
    clips = []
    
    for i, sc in enumerate(scenes):
        narr = sc.get("narration", "")
        vp = sc.get("visual_prompt", "")
        aud_p = os.path.join("outputs/ai_render", f"scene_{i}.mp3")
        
        asyncio.run(_save_tts(narr, voice_id, aud_p))
        aud_clip = AudioFileClip(aud_p)
        dur = aud_clip.duration + 0.3

        img_p = os.path.join("outputs/ai_render", f"frame_{i}.jpg")
        generate_connected_ai_frame(vp, narr, format_type, img_p, scene_idx=i)

        img_clip = ImageClip(img_p).set_duration(dur).set_audio(aud_clip)
        clips.append(img_clip)

    final = concatenate_videoclips(clips, method="compose")
    out_vid = f"outputs/connected_ai_vid_{int(datetime.datetime.now().timestamp())}.mp4"
    final.write_videofile(out_vid, fps=24, codec="libx264", audio_codec="aac")
    return out_vid

# ================= UI & STUDIO DASHBOARD =================
st.markdown("### 🎬 YouTube IQ Studio | <span style='color:green; font-size:16px;'>● AI VIDEO GENERATION ENGINE CONNECTED</span>", unsafe_allow_html=True)
st.divider()

st.sidebar.header("⚙️ Studio Config")
mode = st.sidebar.selectbox("Select Mode", list(MODES.keys()))
niche = st.sidebar.selectbox("Niche", list(HIGH_RPM_NICHES.keys()))
sub_niche = st.sidebar.selectbox("Topic Focus", HIGH_RPM_NICHES[niche])
format_type = st.radio("Video Format", ["Shorts (9:16)", "Long Video (16:9)"])
voice_lbl = st.sidebar.selectbox("AI Voiceover", list(VOICE_OPTIONS.keys()))

tab1, tab2, tab3 = st.tabs([
    "📝 1. Script & Visual Generator",
    "🎥 2. Connected AI Video Studio",
    "🖼️ 3. Auto Thumbnail Studio"
])

with tab1:
    st.subheader("🔥 AI Script & Visual Prompt Studio")
    custom_topic = st.text_input("Video Topic", value=f"The Untold Secrets of {sub_niche}")
    
    if st.button("⚡ Generate AI Script & Visual Prompts"):
        if custom_topic:
            prompt = f"""
            Act as an elite viral video director. Create a 4-scene video script for topic: '{custom_topic}'.
            Return ONLY valid JSON (no markdown ticks):
            {{
              "titles": ["Title 1", "Title 2", "Title 3"],
              "description": "SEO description with hashtags",
              "tags": "tags, viral, video",
              "thumbnail_text": "EXPOSED!",
              "scenes": [
                {{"scene_number": 1, "narration": "Hook narration sentence", "visual_prompt": "3D satellite map view zooming into location"}},
                {{"scene_number": 2, "narration": "Explanation sentence", "visual_prompt": "Cinematic satellite earth rotation view"}},
                {{"scene_number": 3, "narration": "Climax sentence", "visual_prompt": "Detailed historical map overlay animation"}},
                {{"scene_number": 4, "narration": "Conclusion sentence", "visual_prompt": "Zoom out world map view"}}
              ]
            }}
            """
            with st.spinner("Generating connected AI script..."):
                raw = generate_ai_content(prompt)
                if raw:
                    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    try:
                        st.session_state["ai_project"] = json.loads(clean)
                        st.success("✅ Script & Visual Prompts Generated!")
                    except Exception:
                        st.code(raw)

    if "ai_project" in st.session_state:
        p = st.session_state["ai_project"]
        st.write("**🔥 Titles:**", p.get("titles"))
        st.json(p.get("scenes"))

with tab2:
    st.subheader("🎥 Connected AI Video Studio (1080p)")
    if "ai_project" not in st.session_state:
        st.info("पहले Tab 1 में जाकर स्क्रिप्ट जनरेट करें।")
    else:
        if st.button("🚀 Render Connected AI Video Now"):
            scenes = st.session_state["ai_project"].get("scenes", [])
            with st.spinner("Generating AI visuals, realistic voiceover & subtitles..."):
                try:
                    v_path = build_connected_ai_video(scenes, VOICE_OPTIONS[voice_lbl], format_type)
                    st.session_state["connected_video"] = v_path
                    st.success("🎉 AI Video Successfully Rendered!")
                except Exception as e:
                    st.error(f"Render Error: {e}")

        if "connected_video" in st.session_state and os.path.exists(st.session_state["connected_video"]):
            st.video(st.session_state["connected_video"])
            with open(st.session_state["connected_video"], "rb") as vf:
                st.download_button("⬇️ Download AI Video MP4", data=vf, file_name="ai_generated_video.mp4", mime="video/mp4")

with tab3:
    st.subheader("🖼️ Auto Thumbnail Studio")
    if st.button("🎨 Generate Thumbnail"):
        os.makedirs("outputs", exist_ok=True)
        t_out = "outputs/ai_thumb.jpg"
        img = Image.new("RGB", (1280, 720), color=(10, 20, 35))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(50, 50), (1230, 670)], outline=(234, 179, 8), width=6)
        draw.text((90, 120), "AI STUDIO THUMBNAIL", fill=(234, 179, 8))
        draw.rectangle([(90, 450), (1190, 600)], fill=(220, 38, 38))
        draw.text((130, 495), "EXPOSED!", fill=(255, 255, 255))
        img.save(t_out, "JPEG")
        st.image(t_out)
        with open(t_out, "rb") as tf:
            st.download_button("⬇️ Download Thumbnail", data=tf, file_name="ai_thumb.jpg", mime="image/jpeg")
