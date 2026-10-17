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

st.set_page_config(page_title="YouTube IQ - Clean Video Studio", layout="wide")

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
    "1. Viral Map & Geography Shorts": {"lang": "American English", "voice": "en-US-ChristopherNeural", "audience": "Global Viewers"},
    "2. Indian History & Facts": {"lang": "Hindi / Hinglish", "voice": "hi-IN-MadhurNeural", "audience": "Indian Viewers"}
}

NICHES = {
    "Geography & Map Mysteries": ["Why Countries Border Like This", "Secret Islands & Enclaves", "Invisible Lines & Borders"],
    "Global History & Empire": ["How Empires Expanded", "WW2 Battle Maps", "Lost Territories"]
}

VIDEO_STYLES = [
    "Clean Map Animation Style (9:16 Short)", "Cinematic Satellite View"
]

VOICE_OPTIONS = {
    "US Male (Christopher - Pro Narrator)": "en-US-ChristopherNeural",
    "US Female (Jenny - Clear Voice)": "en-US-JennyNeural",
    "Indian Male (Madhur - Hindi/Hinglish)": "hi-IN-MadhurNeural"
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
    st.error("⚠️ Server is busy. Please click again.")
    return None

async def _save_tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)

# Clean Watermark-Free Visual Frame Generator (Geo Map Style)
def generate_clean_map_frame(vis_prompt, sub_text, w, h, path, scene_idx=0):
    # Professional clean satellite dark map background
    img = Image.new("RGB", (w, h), color=(8, 15, 30))
    draw = ImageDraw.Draw(img)
    
    # Subtle Map Grid Lines
    for x in range(0, w, 150):
        draw.line([(x, 0), (x, h)], fill=(15, 30, 55), width=1)
    for y in range(0, h, 150):
        draw.line([(0, y), (w, y)], fill=(15, 30, 55), width=1)

    # Clean Focus Box for Visuals
    center_x, center_y = w // 2, h // 2
    draw.rectangle([(80, center_y - 250), (w - 80, center_y + 150)], fill=(12, 20, 35), outline=(56, 189, 248), width=2)
    
    # Display Visual Focus Text cleanly
    draw.text((110, center_y - 210), f"MAP REGION 0{scene_idx + 1}", fill=(56, 189, 248))
    wrapped_vis = vis_prompt[:120] + ("..." if len(vis_prompt) > 120 else "")
    draw.text((110, center_y - 150), wrapped_vis, fill=(255, 255, 255))

    
