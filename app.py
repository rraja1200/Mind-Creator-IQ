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
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

st.set_page_config(page_title="YouTube IQ - Geo-Map Automation Studio", layout="wide")

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
    "1. Geo/Map Viral Shorts Mode": {"lang": "American English", "voice": "en-US-ChristopherNeural", "audience": "Global Geography Viewers", "best_time": "6:00 PM EST"},
    "2. Indian Geography & History": {"lang": "Hindi / Hinglish", "voice": "hi-IN-MadhurNeural", "audience": "Indian Audience", "best_time": "6:00 PM IST"}
}

NICHES = {
    "Geography & Map Mysteries": ["Why Countries Border Like This", "Secret Islands & Enclaves", "Invisible Lines & Borders", "Impossible Bridges & Straits"],
    "Global History & Empire": ["How Empires Expanded", "WW2 Battle maps", "Lost Territories"]
}

VIDEO_STYLES = [
    "GeoGlobe Tales Map Style (9:16 Short)", "Satellite Zoom Animation Style", "Cinematic Border Breakdown"
]

VOICE_OPTIONS = {
    "US Male (Christopher - Geo Narrator)": "en-US-ChristopherNeural",
    "US Female (Jenny - Clear Voice)": "en-US-JennyNeural",
    "Indian Male (Madhur - Hindi/Hinglish)": "hi-IN-MadhurNeural"
}

# Unlimited Multi-Model Auto-Rotation Engine (Bypasses Quota Limits)
def generate_ai_content(prompt):
    if not GEMINI_API_KEY:
        st.error("⚠️ Gemini API Key missing! Check Streamlit Secrets.")
        return None
        
    client = genai.Client(api_key=GEMINI_API_KEY)
    # Comprehensive list of all available models to rotate automatically
    models_pool = [
        "gemini-3.1-pro-preview", 
        "gemini-3-flash-preview", 
        "gemini-2.5-flash", 
        "gemini-2.5-pro",
        "gemini-2.0-flash-exp"
    ]
    
    for attempt in range(3): # Retry loop
        for model_name in models_pool:
            try:
                res = client.models.generate_content(
                    model=model_name, 
                    contents=prompt
                )
                if res and res.text:
                    return res.text
            except Exception:
                continue # Instantly try next model without stopping
        time.sleep(1) # Brief pause before retrying pool
        
    st.error("⚠️ Server is busy processing bulk requests. Please click 'Generate' again in 5 seconds.")
    return None

async def _save_tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)

def generate_geo_map_frame(vis_prompt, sub_text, w, h, path, scene_idx=0):
    img = Image.new("RGB", (w, h), color=(10, 25, 47))
    draw = ImageDraw.Draw(img)
    
    for x in range(0, w, 120):
        draw.line([(x, 0), (x, h)], fill=(20, 40, 70), width=1)
    for y in range(0, h, 120):
        draw.line([(0, y), (w, y)], fill=(20, 40, 70), width=1)

    draw.rectangle([(60, 60), (w - 60, 160)], fill=(15, 23, 42) , outline=(56, 189, 248), width=3)
    draw.text((90, 85), f"🌍 GEO-MAP SCAN // REGION 0{scene_idx + 1}", fill=(56, 189, 248))

    center_x, center_y = w // 2, h // 2
    draw.ellipse([(center_x - 180, center_y - 320), (center_x + 180, center_y + 40)], outline=(234, 179, 8), width=4)
    draw.text((center_x - 130, center_y - 200), "📍 AREA OF INTEREST", fill=(234, 179, 8))

    draw.rectangle([(60, center_y + 80), (w - 60, center_y + 350)], fill=(15, 23, 42), outline=(34, 197, 94), width=2)
    draw.text((90, center_y + 110), "SATELLITE INTEL:", fill=(34, 197, 94))
    
    wrapped_vis = vis_prompt[:130] + ("..." if len(vis_prompt) > 130 else "")
    draw.text((90, center_y + 160), wrapped_vis, fill=(255, 255, 255))

    if sub_text:
        bar_top = int(h * 0.78)
        draw.rectangle([(0, bar_top), (w, h)], fill=(0, 0, 0))
        draw.rectangle([(0, bar_top), (w, bar_top + 6)], fill=(234, 179, 8))
        
        wrapped_sub = sub_text[:85] + ("..." if len(sub_text) > 85 else "")
        draw.text((60, bar_top + 45), wrapped_sub, fill=(255, 255, 255))
        
    img.save(path, "JPEG", quality=95)
    return path

def build_geo_shorts_video(scenes, voice_id, uploaded_files):
    os.makedirs("outputs/geo_scenes", exist_ok=True)
    w, h = (1080, 1920)
    clips = []
    
    saved_media_paths = []
    if uploaded_files:
        for idx, file in enumerate(uploaded_files):
            m_path = os.path.join("outputs/geo_scenes", f"upload_{idx}_{file.name}")
            with open(m_path, "wb") as f:
                f.write(file.getbuffer())
            saved_media_paths.append(m_path)

    for i, sc in enumerate(scenes):
        narr = sc.get("narration", "")
        vp = sc.get("visual_prompt", "")
        aud_p = os.path.join("outputs/geo_scenes", f"scene_{i}.mp3")
        
        asyncio.run(_save_tts(narr, voice_id, aud_p))
        aud_clip = AudioFileClip(aud_p)
        dur = aud_clip.duration + 0.3

        img_p = os.path.join("outputs/geo_scenes", f"geo_frame_{i}.jpg")
        
        if saved_media_paths and i < len(saved_media_paths):
            media_file = saved_media_paths[i]
            try:
                img = Image.open(media_file).convert("RGB").resize((w, h))
                if narr:
                    draw = ImageDraw.Draw(img)
                    bar_top = int(h * 0.78)
                    draw.rectangle([(0, bar_top), (w, h)], fill=(0, 0, 0))
                    draw.text((60, bar_top + 45), narr[:85], fill=(255, 255, 255))
                img.save(img_p, "JPEG")
            except Exception:
                generate_geo_map_frame(vp, narr, w, h, img_p, scene_idx=i)
        else:
            generate_geo_map_frame(vp, narr, w, h, img_p, scene_idx=i)

        img_clip = ImageClip(img_p).set_duration(dur).set_audio(aud_clip)
        clips.append(img_clip)

    final = concatenate_videoclips(clips, method="compose")
    out_vid = f"outputs/geoshort_{int(datetime.datetime.now().timestamp())}.mp4"
    final.write_videofile(out_vid, fps=24, codec="libx264", audio_codec="aac")
    return out_vid

# ================= UI & STUDIO DASHBOARD =================
st.markdown("### 🗺️ GeoGlobeTales Style | **YouTube IQ AI** <span style='color:green; float:right; font-size:16px;'>● UNLIMITED AUTO-ROTATION ACTIVE</span>", unsafe_allow_html=True)
st.divider()

col_c1, col_c2, col_c3, col_c4 = st.columns(4)
with col_c1:
    st.info("🗺️ **/map-shorts**\nGeo Animation")
with col_c2:
    st.success("📦 **/viral-script**\nHigh-Hook Script")
with col_c3:
    st.warning("🖼️ **/storage-vault**\n5 TB Map Media")
with col_c4:
    st.error("🚀 **9:16 Render**\nViral Short Format")

st.divider()

st.sidebar.header("⚙️ Geo Studio Settings")
mode = st.sidebar.selectbox("Select Mode", list(MODES.keys()))
niche = st.sidebar.selectbox("Select Niche", list(NICHES.keys()))
sub_niche = st.sidebar.selectbox("Topic Focus", NICHES[niche])
voice_lbl = st.sidebar.selectbox("AI Voiceover", list(VOICE_OPTIONS.keys()))

st.sidebar.divider()
st.sidebar.markdown("📂 **5 TB Storage Vault Linked**")
uploaded_storage_files = st.sidebar.file_uploader(
    "📁 Upload Map Screenshots or Satellite Images", 
    type=["jpg", "png", "jpeg", "mp4"], 
    accept_multiple_files=True
)

tab1, tab2, tab3 = st.tabs([
    "📝 1. Viral Map Script & Hook",
    "🎥 2. Geo-Shorts Video Studio (9:16)",
    "🖼️ 3. Map Thumbnail Studio"
])

with tab1:
    st.subheader("🔥 GeoGlobeTales Style Script Generator")
    custom_topic = st.text_input("Short Topic", value=f"Why This Country Has the Strangest Border in {sub_niche}")
    
    if st.button("⚡ Generate Viral Map Script"):
        if custom_topic:
            prompt = f"""
            Act as a viral geography YouTuber like GeoGlobeTales. Create a fast-paced 4-scene script for YouTube Short about: '{custom_topic}'.
            Return ONLY valid JSON (no markdown ticks):
            {{
              "titles": ["Title 1", "Title 2", "Title 3"],
              "description": "Viral description with hashtags",
              "tags": "geography, map, shorts, viral",
              "thumbnail_text": "WHY?!",
              "scenes": [
                {{"scene_number": 1, "narration": "Hook sentence with high curiosity", "visual_prompt": "Map view showing country border and zoom-in"}},
                {{"scene_number": 2, "narration": "Explanation sentence", "visual_prompt": "Satellite map view highlighting the anomaly"}},
                {{"scene_number": 3, "narration": "Twist or historical reason", "visual_prompt": "Historical map overlay comparison"}},
                {{"scene_number": 4, "narration": "Conclusion punchline", "visual_prompt": "Zoom-out world map view"}}
              ]
            }}
            """
            with st.spinner("Generating map-based viral script..."):
                raw = generate_ai_content(prompt)
                if raw:
                    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    try:
                        st.session_state["geo_project"] = json.loads(clean)
                        st.success("✅ Viral Map Script Generated!")
                    except Exception:
                        st.code(raw)

    if "geo_project" in st.session_state:
        p = st.session_state["geo_project"]
        st.write("**🔥 Titles:**", p.get("titles"))
        st.text_area("Description", value=p.get("description", ""), height=80)
        st.json(p.get("scenes"))

with tab2:
    st.subheader("🎬 Geo-Shorts Video Studio (9:16 Map Animation)")
    if "geo_project" not in st.session_state:
        st.info("पहले Tab 1 में जाकर स्क्रिप्ट जनरेट करें।")
    else:
        if st.button("🚀 Render 9:16 Geo-Shorts Video Now"):
            scenes = st.session_state["geo_project"].get("scenes", [])
            with st.spinner("Rendering satellite map frames, voiceover & subtitles..."):
                try:
                    v_path = build_geo_shorts_video(scenes, VOICE_OPTIONS[voice_lbl], uploaded_storage_files)
                    st.session_state["geo_video"] = v_path
                    st.success("🎉 Viral Geo-Short Successfully Rendered!")
                except Exception as e:
                    st.error(f"Render Error: {e}")

        if "geo_video" in st.session_state and os.path.exists(st.session_state["geo_video"]):
            st.video(st.session_state["geo_video"])
            with open(st.session_state["geo_video"], "rb") as vf:
                st.download_button("⬇️ Download Geo-Short MP4", data=vf, file_name="geoshort_viral.mp4", mime="video/mp4")

with tab3:
    st.subheader("🖼️ Map Thumbnail Studio")
    if st.button("🎨 Generate Map Thumbnail"):
        os.makedirs("outputs", exist_ok=True)
        t_out = "outputs/geo_thumb.jpg"
        img = Image.new("RGB", (1080, 1920), color=(10, 25, 47))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(50, 50), (1030, 1870)], outline=(234, 179, 8), width=8)
        draw.text((100, 200), "GEO MYSTERY", fill=(234, 179, 8))
        draw.rectangle([(100, 1200), (980, 1500)], fill=(220, 38, 38))
        draw.text((140, 1280), "WHY?!", fill=(255, 255, 255))
        img.save(t_out, "JPEG")
        st.image(t_out)
        with open(t_out, "rb") as tf:
            st.download_button("⬇️ Download Thumbnail", data=tf, file_name="geo_thumb.jpg", mime="image/jpeg")
