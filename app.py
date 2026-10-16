import os
import json
import asyncio
import sqlite3
import datetime
from io import BytesIO
import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
import edge_tts

try:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

from google import genai
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or st.secrets.get("GEMINI_API_KEY", None)

st.set_page_config(page_title="YouTube IQ - Full AI Automation", layout="wide")

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
    "1. USA Mode": {"lang": "American English", "voice": "en-US-ChristopherNeural", "audience": "United States viewers (High RPM)", "best_time": "6:00 PM EST"},
    "2. Indian Audience Mode": {"lang": "Hindi / Hinglish", "voice": "hi-IN-MadhurNeural", "audience": "Indian viewers", "best_time": "6:00 PM IST"},
    "3. Worldwide Mode": {"lang": "Global English", "voice": "en-GB-RyanNeural", "audience": "Global audience", "best_time": "3:00 PM UTC"},
    "4. High-RPM Niche Mode": {"lang": "US English", "voice": "en-US-GuyNeural", "audience": "Tier-1 Advertisers", "best_time": "7:00 PM EST"}
}

NICHES = {
    "Gaming": ["GTA", "Minecraft", "BGMI / PUBG", "Roblox", "Racing Games", "Horror Games"],
    "Finance & Business": ["Personal Finance", "Stock Market", "SaaS Tools", "Startup Case Studies"],
    "Technology & AI Tools": ["AI Software Reviews", "Coding & Automation", "Smartphone Comparisons"],
    "Education & Documentary": ["History", "Science", "Geopolitics", "Space"]
}

VIDEO_STYLES = ["Cinematic Video", "Realistic Video", "2D Animation", "3D Animation", "Documentary", "Gaming Videos"]

VOICE_OPTIONS = {
    "US Male (Christopher)": "en-US-ChristopherNeural",
    "Indian Male (Madhur)": "hi-IN-MadhurNeural",
    "Indian Female (Swara)": "hi-IN-SwaraNeural"
}

def generate_ai_content(prompt):
    if not GEMINI_API_KEY:
        st.error("API Key नहीं मिली! Streamlit Secrets में GEMINI_API_KEY डालें।")
        return None
    client = genai.Client(api_key=GEMINI_API_KEY)
    for model in ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-flash"]:
        try:
            res = client.models.generate_content(model=model, contents=prompt)
            return res.text
        except Exception:
            continue
    st.error("सभी फ्री मॉडल्स की लिमिट पूरी हो गई है।")
    return None

def generate_scene_image(vis_prompt, sub_text, w, h, path):
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(vis_prompt + ', 8k, highly detailed')}?width={w}&height={h}&nologo=true"
    res = requests.get(url, timeout=30)
    img = Image.open(BytesIO(res.content)).convert("RGB").resize((w, h))
    if sub_text:
        draw = ImageDraw.Draw(img)
        draw.rectangle([(0, int(h*0.8)), (w, h)], fill=(0,0,0))
        draw.text((40, int(h*0.83)), sub_text[:80], fill=(255,255,0))
    img.save(path, "JPEG", quality=95)
    return path

async def _save_tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)

def build_full_video(scenes, style, voice_id):
    os.makedirs("outputs/scenes", exist_ok=True)
    clips = []
    for i, sc in enumerate(scenes):
        narr = sc.get("narration", "")
        vp = f"{sc.get('visual_prompt', '')}, {style}"
        img_p, aud_p = f"outputs/scenes/{i}.jpg", f"outputs/scenes/{i}.mp3"
        generate_scene_image(vp, narr, 1920, 1080, img_p)
        asyncio.run(_save_tts(narr, voice_id, aud_p))
        aud = AudioFileClip(aud_p)
        clips.append(ImageClip(img_p).set_duration(aud.duration + 0.3).set_audio(aud))
    final = concatenate_videoclips(clips, method="compose")
    out_vid = f"outputs/vid_{int(datetime.datetime.now().timestamp())}.mp4"
    final.write_videofile(out_vid, fps=24, codec="libx264", audio_codec="aac")
    return out_vid

st.title("🚀 YouTube IQ — AI Automation Studio")
mode = st.sidebar.selectbox("Select Mode", list(MODES.keys()))
niche = st.sidebar.selectbox("Select Niche", list(NICHES.keys()))
sub_n = st.sidebar.selectbox("Sub-Niche", NICHES[niche])

topic = st.text_input("Video Topic", placeholder="e.g., Future of AI in 2026")
style = st.selectbox("Video Style", VIDEO_STYLES)
voice_lbl = st.selectbox("Voice", list(VOICE_OPTIONS.keys()))

if st.button("⚡ Generate Script & Scenes"):
    if topic:
        prompt = f"""Create a 3-scene YouTube script for topic: {topic}. Return ONLY valid JSON:
        {{"titles": ["Title 1"], "description": "SEO desc", "tags": "tags", "scenes": [{"scene_number": 1, "narration": "text", "visual_prompt": "visual"}]}}"""
        raw = generate_ai_content(prompt)
        if raw:
            clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            st.session_state["proj"] = json.loads(clean)
            st.success("Script Generated!")

if "proj" in st.session_state:
    st.json(st.session_state["proj"])
    if st.button("🎬 Render Video (1080p MP4)"):
        with st.spinner("Rendering video..."):
            path = build_full_video(st.session_state["proj"]["scenes"], style, VOICE_OPTIONS[voice_lbl])
            st.session_state["vid"] = path
            st.success("Video Ready!")

if "vid" in st.session_state and os.path.exists(st.session_state["vid"]):
    st.video(st.session_state["vid"])
    
