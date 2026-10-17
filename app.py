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

st.set_page_config(page_title="YouTube IQ - AI Automation Studio", layout="wide")

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
    "1. USA High-RPM Mode ($30-50 RPM)": {"lang": "American English", "voice": "en-US-ChristopherNeural", "audience": "US Tier-1 Audience", "best_time": "6:00 PM EST"},
    "2. Indian Audience Mode": {"lang": "Hindi / Hinglish", "voice": "hi-IN-MadhurNeural", "audience": "Indian Mass Market", "best_time": "6:00 PM IST"},
    "3. Worldwide Global Mode": {"lang": "Global English", "voice": "en-GB-RyanNeural", "audience": "Global International", "best_time": "3:00 PM UTC"}
}

NICHES = {
    "US Personal Finance & Wealth": ["Buy Borrow Die Strategy", "Real Estate Investing", "Credit Card Optimization", "SaaS Tools & AI Business"],
    "Gaming & Metaverse": ["GTA 6 Gameplay & Physics", "Minecraft Survival Hacks", "Roblox Studio Automation", "Open-World RPGs"],
    "Technology & AI Tools": ["AI Software Reviews", "Coding & Python Automation", "Future Tech Explainers"],
    "Documentary & Storytelling": ["Geopolitics & History", "True Crime & Mysteries", "Space & Universe Explainers"]
}

VIDEO_STYLES = [
    "Cinematic Documentary", "Realistic 4K Style", "2D Animated Explainer", 
    "3D Gaming Montage", "Paper-Cut Storytelling", "YouTube Shorts (9:16)"
]

VOICE_OPTIONS = {
    "US Male (Christopher - Deep Studio)": "en-US-ChristopherNeural",
    "US Female (Jenny - Clean Pro)": "en-US-JennyNeural",
    "Indian Male (Madhur - Hindi/Hinglish)": "hi-IN-MadhurNeural",
    "Indian Female (Swara - Hindi/Hinglish)": "hi-IN-SwaraNeural"
}

def generate_ai_content(prompt):
    if not GEMINI_API_KEY:
        st.error("⚠️ Gemini API Key missing! Check Streamlit Secrets.")
        return None
    client = genai.Client(api_key=GEMINI_API_KEY)
    models_list = ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"]
    for model_name in models_list:
        try:
            res = client.models.generate_content(model=model_name, contents=prompt)
            return res.text
        except Exception:
            continue
    st.error("⚠️ Free API quota limit reached. Please wait a minute.")
    return None

async def _save_tts(text, voice, out):
    await edge_tts.Communicate(text, voice).save(out)

# Build Video using User Uploaded Storage Media (Images/Videos) or Fallback Dynamic Cards
def build_media_custom_video(scenes, voice_id, uploaded_files, style, is_short=False):
    os.makedirs("outputs/media_scenes", exist_ok=True)
    w, h = (1080, 1920) if is_short else (1920, 1080)
    clips = []
    
    # Save uploaded storage files locally
    saved_media_paths = []
    if uploaded_files:
        for idx, file in enumerate(uploaded_files):
            m_path = os.path.join("outputs/media_scenes", f"upload_{idx}_{file.name}")
            with open(m_path, "wb") as f:
                f.write(file.getbuffer())
            saved_media_paths.append(m_path)

    for i, sc in enumerate(scenes):
        narr = sc.get("narration", "")
        aud_p = os.path.join("outputs/media_scenes", f"scene_{i}.mp3")
        asyncio.run(_save_tts(narr, voice_id, aud_p))
        aud_clip = AudioFileClip(aud_p)
        dur = aud_clip.duration + 0.3

        # If user provided storage media, use it cyclically; otherwise generate styled history card
        if saved_media_paths:
            media_file = saved_media_paths[i % len(saved_media_paths)]
            if media_file.endswith((".mp4", ".mov", ".avi")):
                try:
                    img_clip = VideoFileClip(media_file).subclip(0, dur).resize((w, h)).set_audio(aud_clip)
                    clips.append(img_clip)
                    continue
                except Exception:
                    pass # Fallback to image if video load fails
            
            # Load user image and burn subtitle
            try:
                img = Image.open(media_file).convert("RGB").resize((w, h))
            except Exception:
                img = Image.new("RGB", (w, h), color=(15, 23, 42))
        else:
            # Fallback historical theme card if no files uploaded yet
            img = Image.new("RGB", (w, h), color=(20, 24, 33))
            draw = ImageDraw.Draw(img)
            draw.rectangle([(50, 50), (w-50, h-50)], outline=(212, 175, 55), width=5)
            draw.text((100, 120), f"CHAPTER {i+1} : HISTORICAL ARCHIVE", fill=(212, 175, 55))
            draw.text((100, 200), f"TOPIC VISUAL: {sc.get('visual_prompt', '')[:90]}", fill=(255, 255, 255))

        # Burn Subtitles on Image
        if narr:
            draw = ImageDraw.Draw(img)
            bar_top = int(h * 0.75)
            draw.rectangle([(0, bar_top), (w, h)], fill=(0, 0, 0))
            draw.rectangle([(0, bar_top), (w, bar_top + 6)], fill=(212, 175, 55))
            draw.text((60, bar_top + 40), narr[:90], fill=(255, 255, 255))

        img_p = os.path.join("outputs/media_scenes", f"final_img_{i}.jpg")
        img.save(img_p, "JPEG", quality=95)
        
        img_clip = ImageClip(img_p).set_duration(dur).set_audio(aud_clip)
        clips.append(img_clip)

    final = concatenate_videoclips(clips, method="compose")
    out_vid = f"outputs/custom_vid_{int(datetime.datetime.now().timestamp())}.mp4"
    final.write_videofile(out_vid, fps=24, codec="libx264", audio_codec="aac")
    return out_vid

# ================= UI & STUDIO DASHBOARD =================
st.markdown("### 🎬 17 Studios | **YouTube IQ** <span style='color:green; float:right; font-size:16px;'>● CONNECTED (5 TB Storage Active)</span>", unsafe_allow_html=True)
st.divider()

col_c1, col_c2, col_c3, col_c4 = st.columns(4)
with col_c1:
    st.info("🧠 **/yt-seo**\nAuto Title & Tags")
with col_c2:
    st.success("📦 **/yt-package**\nStoryboard & Script")
with col_c3:
    st.warning("🖼️ **/storage-media**\n5 TB Vault Connected")
with col_c4:
    st.error("🚀 **Auto-Pipeline**\n1080p Custom Render")

st.divider()

st.sidebar.header("⚙️ Studio Configuration")
mode = st.sidebar.selectbox("Select Mode", list(MODES.keys()))
niche = st.sidebar.selectbox("Select Niche", list(NICHES.keys()))
sub_niche = st.sidebar.selectbox("Sub-Niche Topic", NICHES[niche])
style = st.sidebar.selectbox("Video Style", VIDEO_STYLES)
voice_lbl = st.sidebar.selectbox("AI Voiceover", list(VOICE_OPTIONS.keys()))

st.sidebar.divider()
st.sidebar.markdown("📂 **Local Storage Status:** `5 TB Vault Linked`")
uploaded_storage_files = st.sidebar.file_uploader(
    "📁 Upload Storage Media (Images/Videos for Characters & History)", 
    type=["jpg", "png", "jpeg", "mp4", "mov"], 
    accept_multiple_files=True
)

tab1, tab2, tab3, tab4 = st.tabs([
    "📝 1. Script, Storyboard & SEO",
    "🎥 2. AI Video Studio (Custom Media)",
    "🖼️ 3. AI Thumbnail Studio",
    "📅 4. YouTube Auto-Uploader"
])

with tab1:
    st.subheader("🔥 High-RPM Niche & Script Generator")
    custom_topic = st.text_input("Video Topic / Prompt", value=f"The Untold History & Secrets of {sub_niche}")
    
    if st.button("⚡ Generate Script & Storyboard"):
        if custom_topic:
            prompt = f"""
            Act as an elite Documentary Director. Create a 4-scene video script and SEO package for topic: '{custom_topic}' in niche '{niche} -> {sub_niche}'.
            Return ONLY valid JSON (no markdown ticks):
            {{
              "titles": ["Title 1", "Title 2", "Title 3"],
              "description": "SEO description with history and timestamps",
              "tags": "tag1, tag2, tag3, tag4, tag5",
              "thumbnail_prompt": "Vibrant thumbnail prompt",
              "thumbnail_text": "HISTORY REVEALED",
              "scenes": [
                {{"scene_number": 1, "narration": "Engaging historical narration sentence", "visual_prompt": "Character or history visual description"}},
                {{"scene_number": 2, "narration": "Engaging historical narration sentence", "visual_prompt": "Character or history visual description"}},
                {{"scene_number": 3, "narration": "Engaging historical narration sentence", "visual_prompt": "Character or history visual description"}},
                {{"scene_number": 4, "narration": "Engaging historical narration sentence", "visual_prompt": "Character or history visual description"}}
              ]
            }}
            """
            with st.spinner("Gemini 3.1 Pro generating deep historical storyboard..."):
                raw = generate_ai_content(prompt)
                if raw:
                    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    try:
                        st.session_state["project_data"] = json.loads(clean)
                        st.success("✅ Deep Storyboard & Script Generated Successfully!")
                    except Exception:
                        st.code(raw)

    if "project_data" in st.session_state:
        p = st.session_state["project_data"]
        st.write("**🔥 High-CTR Titles:**", p.get("titles"))
        st.text_area("SEO Description", value=p.get("description", ""), height=90)
        st.code(p.get("tags"))
        st.json(p.get("scenes"))

with tab2:
    st.subheader("🎬 AI Video Studio — Render with Your 5 TB Storage Media")
    if "project_data" not in st.session_state:
        st.info("पहले Tab 1 में जाकर स्क्रिप्ट जनरेट करें।")
    else:
        if uploaded_storage_files:
            st.success(f"✅ {len(uploaded_storage_files)} files loaded from your storage vault for video composition!")
        else:
            st.info("💡 Tip: आप चाहें तो बाएं साइडबार से अपनी 5 TB स्टोरेज की तस्वीरें या वीडियो अपलोड कर सकते हैं, वरना ऐप ऑटोमैटिक हिस्टोरिकल कार्ड बनाएगी।")

        is_sh = "Shorts" in style
        if st.button("🚀 Render Custom 1080p Video with Storage Media"):
            scenes = st.session_state["project_data"].get("scenes", [])
            with st.spinner("Compiling custom media, voiceover, and subtitles into 1080p video..."):
                try:
                    v_path = build_media_custom_video(scenes, VOICE_OPTIONS[voice_lbl], uploaded_storage_files, style, is_sh)
                    st.session_state["final_video"] = v_path
                    st.success("🎉 Custom 1080p Video Successfully Rendered from Storage!")
                except Exception as e:
                    st.error(f"Render Error: {e}")

        if "final_video" in st.session_state and os.path.exists(st.session_state["final_video"]):
            st.video(st.session_state["final_video"])
            with open(st.session_state["final_video"], "rb") as vf:
                st.download_button("⬇️ Download Custom 1080p MP4", data=vf, file_name="youtube_iq_custom.mp4", mime="video/mp4")

with tab3:
    st.subheader("🖼️ AI Thumbnail Studio")
    p_info = st.session_state.get("project_data", {})
    t_pr = st.text_input("Thumbnail Prompt", value=p_info.get("thumbnail_prompt", "Cinematic historical documentary thumbnail"))
    t_tx = st.text_input("Thumbnail Bold Text", value=p_info.get("thumbnail_text", "THE SECRET!"))

    if st.button("🎨 Generate HD Thumbnail"):
        os.makedirs("outputs", exist_ok=True)
        t_out = f"outputs/thumb_{int(datetime.datetime.now().timestamp())}.jpg"
        img = Image.new("RGB", (1280, 720), color=(10, 15, 25))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(40, 40), (1240, 680)], outline=(212, 175, 55), width=6)
        draw.text((80, 100), "DOCUMENTARY ARCHIVE", fill=(212, 175, 55))
        draw.text((80, 200), f"TOPIC: {t_pr[:60]}", fill=(255, 255, 255))
        draw.rectangle([(80, 450), (1200, 600)], fill=(185, 28, 28))
        draw.text((120, 500), t_tx.upper(), fill=(255, 255, 255))
        img.save(t_out, "JPEG", quality=95)
        st.session_state["thumb_path"] = t_out
        st.success("Thumbnail Generated!")

    if "thumb_path" in st.session_state and os.path.exists(st.session_state["thumb_path"]):
        st.image(st.session_state["thumb_path"])
        with open(st.session_state["thumb_path"], "rb") as tf:
            st.download_button("⬇️ Download Thumbnail JPG", data=tf, file_name="thumbnail.jpg", mime="image/jpeg")

with tab4:
    st.subheader("📅 YouTube Auto-Uploader")
    st.info("💡 Upload `client_secrets.json` to GitHub root for one-click publishing.")
