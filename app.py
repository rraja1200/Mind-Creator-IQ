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

# MoviePy for real 1080p MP4 rendering (compatible with MoviePy v1 & v2)
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

# ================= 1. CONFIG & DATABASE =================
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

# ================= 2. MODES, NICHES & VOICES =================
MODES = {
    "1. USA Mode": {
        "lang": "American English",
        "voice": "en-US-ChristopherNeural",
        "audience": "United States viewers (High RPM, fast-paced hooks)",
        "best_time": "6:00 PM - 9:00 PM EST (3:30 AM - 6:30 AM IST)"
    },
    "2. Indian Audience Mode": {
        "lang": "Hindi / Hinglish",
        "voice": "hi-IN-MadhurNeural",
        "audience": "Indian viewers (Mass appeal, relatable storytelling)",
        "best_time": "5:00 PM - 8:00 PM IST"
    },
    "3. Worldwide Audience Mode": {
        "lang": "Global Simple English",
        "voice": "en-GB-RyanNeural",
        "audience": "International global audience",
        "best_time": "2:00 PM - 5:00 PM UTC"
    },
    "4. Regular Mode": {
        "lang": "Hindi / English",
        "voice": "hi-IN-SwaraNeural",
        "audience": "Standard YouTube viewers",
        "best_time": "6:00 PM Local Time"
    },
    "5. High-RPM Niche Mode": {
        "lang": "Professional US English",
        "voice": "en-US-GuyNeural",
        "audience": "Tier-1 High-Intent Advertisers (Finance, SaaS, Enterprise Tech)",
        "best_time": "7:00 PM EST"
    }
}

NICHES = {
    "Gaming": ["GTA", "Minecraft", "Roblox", "Battle Royale (BGMI / PUBG / Free Fire)", "Racing Games", "Horror Games", "Open-World Gaming", "Simulator Games", "Action Games"],
    "Finance & Business": ["Personal Finance", "Stock Market & Investing", "SaaS & B2B Tools", "Real Estate", "Startup Case Studies", "Wealth Management"],
    "Technology & AI Tools": ["AI Software Reviews", "Coding & Automation", "Smartphone Comparisons", "Future Tech", "Cybersecurity", "Gadget Explainers"],
    "Education & Documentary": ["History Documentaries", "Science Explainers", "Geopolitics & News Explainers", "Psychology", "Space & Astronomy"],
    "Animation & Storytelling": ["2D Animation Stories", "3D Animation", "Horror Storytelling", "Paper-Cut Animation", "Stick-Figure Explainers"],
    "Entertainment & Lifestyle": ["Travel", "Food", "Fitness", "Sports Analysis", "Music Videos"]
}

VIDEO_STYLES = [
    "2D Animation", "3D Animation", "Realistic Video", "Cinematic Video",
    "Paper-Cut Animation", "Stick-Figure Animation", "Gaming Videos",
    "Documentary", "Storytelling", "Music Videos", "Educational Videos",
    "Shorts (9:16 Vertical)", "Long Videos (16:9 Horizontal)"
]

VOICE_OPTIONS = {
    "US Male (Christopher - Deep Documentary)": "en-US-ChristopherNeural",
    "US Female (Jenny - Clear Explainer)": "en-US-JennyNeural",
    "Indian Male (Madhur - Hindi/Hinglish)": "hi-IN-MadhurNeural",
    "Indian Female (Swara - Hindi/Hinglish)": "hi-IN-SwaraNeural",
    "Indian English Male (Prabhat)": "en-IN-PrabhatNeural",
    "UK Male (Ryan - Global Narrator)": "en-GB-RyanNeural"
}

# ================= 3. GEMINI 3.1 PRO ENGINE =================
def generate_ai_content(prompt):
    if not GEMINI_API_KEY:
        st.error("API Key नहीं मिली! कृपया Streamlit Secrets या `.env` में `GEMINI_API_KEY` डालें।")
        return None

    client = genai.Client(api_key=GEMINI_API_KEY)
    models_priority = [
        "gemini-3.1-pro-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash"
    ]

    for model_name in models_priority:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            st.toast(f"🧠 Powered by: {model_name}")
            return response.text
        except Exception:
            continue

    st.error("अभी सभी फ्री मॉडल्स की प्रति-मिनट लिमिट पूरी हो गई है। 60 सेकंड बाद दोबारा क्लिक करें।")
    return None

# ================= 4. FREE AI IMAGE, VOICE & 1080p VIDEO ENGINE =================
def generate_scene_image(visual_prompt, subtitle_text, width, height, filepath):
    full_prompt = f"{visual_prompt}, high quality, ultra detailed, 8k resolution, no text"
    encoded = requests.utils.quote(full_prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
    res = requests.get(url, timeout=45)
    img = Image.open(BytesIO(res.content)).convert("RGB").resize((width, height))

    if subtitle_text:
        draw = ImageDraw.Draw(img)
        bar_top = int(height * 0.78)
        draw.rectangle([(0, bar_top), (width, height)], fill=(0, 0, 0))
        font = ImageFont.load_default()
        wrapped = subtitle_text[:95] + ("..." if len(subtitle_text) > 95 else "")
        draw.text((40, bar_top + 35), wrapped, fill=(255, 255, 0), font=font)

    img.save(filepath, "JPEG", quality=95)
    return filepath

async def _save_tts(text, voice, out_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)

def generate_voiceover(text, voice, out_path):
    asyncio.run(_save_tts(text, voice, out_path))
    return out_path

def build_full_video(scenes, style, voice_id, burn_subs=True, is_short=False):
    os.makedirs("outputs/scenes", exist_ok=True)
    width, height = (1080, 1920) if is_short else (1920, 1080)
    clips = []

    for idx, sc in enumerate(scenes):
        narration = sc.get("narration", "").strip()
        vis_prompt = f"{sc.get('visual_prompt', '')}, {style} style"
        if not narration:
            continue

        img_path = f"outputs/scenes/scene_{idx}.jpg"
        aud_path = f"outputs/scenes/scene_{idx}.mp3"

        generate_scene_image(vis_prompt, narration if burn_subs else "", width, height, img_path)
        generate_voiceover(narration, voice_id, aud_path)

        audio_clip = AudioFileClip(aud_path)
        duration = audio_clip.duration + 0.3

        try:
            img_clip = ImageClip(img_path).set_duration(duration).set_audio(audio_clip)
        except AttributeError:
            img_clip = ImageClip(img_path).with_duration(duration).with_audio(audio_clip)

        clips.append(img_clip)

    final_path = f"outputs/video_{int(datetime.datetime.now().timestamp())}.mp4"
    final_video = concatenate_videoclips(clips, method="compose")
    final_video.write_videofile(final_path, fps=24, codec="libx264", audio_codec="aac")
    return final_path

# ================= 5. YOUTUBE OAUTH & ANALYTICS =================
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def authenticate_youtube_channel(channel_label):
    os.makedirs("tokens", exist_ok=True)
    token_path = os.path.join("tokens", f"token_{channel_label}.json")
    creds = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists("client_secrets.json"):
                st.error("`client_secrets.json` नहीं मिली! Google Cloud Console से डाउनलोड करके इसी फोल्डर में रखें।")
                return None
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)

# ================= 6. MAIN UI & SIDEBAR =================
st.title("🚀 YouTube IQ — Complete Zero-Budget AI Automation System")

st.sidebar.header("🌍 1. Select Operating Mode")
selected_mode = st.sidebar.selectbox("Mode", list(MODES.keys()))
st.sidebar.caption(f"🎯 **Audience:** {MODES[selected_mode]['audience']}")
st.sidebar.caption(f"⏰ **Best Upload Time:** {MODES[selected_mode]['best_time']}")

st.sidebar.header("🎮 2. Niche & Sub-Niche")
selected_niche = st.sidebar.selectbox("Primary Niche", list(NICHES.keys()))
selected_sub_niche = st.sidebar.selectbox("Sub-Niche / Category", NICHES[selected_niche])

if selected_niche == "Gaming":
    custom_game = st.sidebar.text_input("Enter Specific Game (e.g., GTA 6, BGMI, PUBG, Minecraft)", value=selected_sub_niche)
else:
    custom_game = selected_sub_niche

st.sidebar.divider()
st.sidebar.header("📺 3. Multi-Channel Manager")
os.makedirs("tokens", exist_ok=True)
saved_channels = [f.replace("token_", "").replace(".json", "") for f in os.listdir("tokens") if f.startswith("token_")]
active_channel = st.sidebar.selectbox("Active Channel", ["None"] + saved_channels)
new_ch = st.sidebar.text_input("Add Channel Alias (e.g., My_USA_Channel)")
if st.sidebar.button("🔗 Connect YouTube Channel"):
    if new_ch:
        if authenticate_youtube_channel(new_ch):
            st.sidebar.success(f"Connected: {new_ch}")
            st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📝 1. Script, Custom Request & SEO",
    "🎥 2. AI Video Studio (1080p MP4)",
    "🖼️ 3. AI Thumbnail Studio",
    "📅 4. Smart Upload Scheduler",
    "📊 5. Analytics & AI Growth Coach"
])

# ---------------- TAB 1: SCRIPT & CUSTOM REQUEST ----------------
with tab1:
    st.subheader("🧠 Gemini 3.1 Pro — Script, Scenes & SEO Engine")

    if selected_mode == "5. High-RPM Niche Mode":
        st.info("💡 **High-RPM Research Note:** RPM विज्ञापनदाताओं की बोली और दर्शकों के देश (USA/UK) पर निर्भर करता है। यह टूल उच्च विज्ञापन मांग वाले विषयों की पहचान करता है, लेकिन किसी निश्चित कमाई की गारंटी नहीं देता।")
        if st.button("🔍 Research High-Paying Topics in this Niche"):
            with st.spinner("Gemini 3.1 Pro बाज़ार का विश्लेषण कर रहा है..."):
                res = generate_ai_content(f"Suggest 5 high-CPC/high-RPM video topics in {selected_niche} ({custom_game}) for {MODES[selected_mode]['audience']}. Explain advertiser demand clearly.")
                st.markdown(res)

    c1, c2 = st.columns(2)
    with c1:
        video_style = st.selectbox("Video Style", VIDEO_STYLES)
        language = st.text_input("Script Language", value=MODES[selected_mode]["lang"])
        scene_count = st.slider("Number of Scenes", min_value=3, max_value=12, value=5)
    with c2:
        topic = st.text_input("Video Topic", placeholder="e.g., Why GTA 6 Physics Will Change Gaming Forever")
        custom_req = st.text_area("✨ Custom Video Request (अपनी पसंद का कोई भी नया स्टाइल या खास निर्देश लिखें)", placeholder="उदाहरण: स्टोरीटेलिंग एकदम सस्पेंस वाली रखो और हर सीन में सिनेमैटिक डार्क लाइटिंग के विजुअल प्रॉम्प्ट दो...")

    if st.button("⚡ Generate Script, Scenes & Full SEO"):
        if not topic:
            st.warning("कृपया पहले Topic लिखें!")
        else:
            prompt = f"""
            You are an elite YouTube Automation Director using Gemini 3.1 Pro.
            Return ONLY valid JSON (no markdown backticks) with this exact structure:
            {{
              "titles": ["title 1", "title 2", "title 3", "title 4", "title 5"],
              "description": "Full SEO description with chapters and keywords",
              "tags": "tag1, tag2, tag3, tag4, tag5, tag6, tag7, tag8, tag9, tag10",
              "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5",
              "thumbnail_visual_prompt": "Detailed English visual prompt for thumbnail without text",
              "thumbnail_text": "3 PUNCHY WORDS",
              "scenes": [
                {{"scene_number": 1, "narration": "Exact spoken line in {language}", "visual_prompt": "Detailed English visual description matching {video_style}"}}
              ]
            }}
            Generate exactly {scene_count} scenes.
            Mode: {selected_mode} | Niche: {selected_niche} ({custom_game}) | Style: {video_style}
            Topic: {topic}
            Custom User Request: {custom_req if custom_req else "High retention hook and pacing"}
            """
            with st.spinner("Gemini 3.1 Pro आपकी स्क्रिप्ट और सीन्स तैयार कर रहा है..."):
                raw = generate_ai_content(prompt)
                if raw:
                    clean = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
                    try:
                        data = json.loads(clean)
                        st.session_state["project"] = data
                        st.session_state["style"] = video_style
                        st.session_state["topic"] = topic
                        st.success("✅ स्क्रिप्ट, सीन और SEO तैयार हो गए! अब Tab 2 में जाकर वीडियो बनाएं।")
                    except Exception:
                        st.write(raw)

    if "project" in st.session_state:
        p = st.session_state["project"]
        st.write("**🔥 Suggested High-CTR Titles:**", p.get("titles", []))
        st.text_area("SEO Description", value=p.get("description", ""), height=100)
        st.code(p.get("tags", "") + "\n" + p.get("hashtags", ""))
        st.json(p.get("scenes", []))

# ---------------- TAB 2: AI VIDEO STUDIO ----------------
with tab2:
    st.subheader("🎥 Free AI Video Studio (Voiceover + Subtitles + 1080p MP4)")
    if "project" not in st.session_state:
        st.info("पहले Tab 1 में जाकर अपनी स्क्रिप्ट और सीन्स जनरेट करें।")
    else:
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            selected_voice_label = st.selectbox("Select AI Voiceover", list(VOICE_OPTIONS.keys()))
            voice_id = VOICE_OPTIONS[selected_voice_label]
        with col_v2:
            aspect = st.radio("Video Format", ["16:9 Long Video (1920x1080)", "9:16 YouTube Short (1080x1920)"])
        with col_v3:
            burn_subs = st.checkbox("Auto-Burn Subtitles on Video", value=True)

        if st.button("🎬 Render Full 1080p MP4 Video Now (100% Free)"):
            scenes = st.session_state["project"].get("scenes", [])
            style = st.session_state.get("style", "Cinematic Video")
            is_short = "9:16" in aspect
            with st.spinner("AI सीन्स, वॉइसओवर और 1080p वीडियो रेंडर कर रहा है (इसमें 1-2 मिनट लगेंगे)..."):
                try:
                    vid_path = build_full_video(scenes, style, voice_id, burn_subs, is_short)
                    st.session_state["last_video"] = vid_path
                    st.success("🎉 1080p HD वीडियो सफलतापूर्वक तैयार हो गया!")
                except Exception as e:
                    st.error(f"Video Rendering Error: {e}")

        if "last_video" in st.session_state and os.path.exists(st.session_state["last_video"]):
            st.video(st.session_state["last_video"])
            with open(st.session_state["last_video"], "rb") as vf:
                st.download_button("⬇️ Download 1080p MP4 Video", data=vf, file_name="youtube_iq_video.mp4", mime="video/mp4")

# ---------------- TAB 3: AI THUMBNAIL STUDIO ----------------
with tab3:
    st.subheader("🖼️ Free 1280x720 HD Thumbnail Studio")
    p_data = st.session_state.get("project", {})
    t_prompt = st.text_area("Thumbnail Visual Prompt", value=p_data.get("thumbnail_visual_prompt", "Dramatic cinematic YouTube thumbnail, vibrant glowing contrast, 8k"))
    t_text = st.text_input("Thumbnail Bold Text", value=p_data.get("thumbnail_text", "MUST WATCH!"))

    if st.button("🎨 Generate HD Thumbnail"):
        with st.spinner("Generating HD Thumbnail..."):
            os.makedirs("outputs", exist_ok=True)
            t_path = f"outputs/thumb_{int(datetime.datetime.now().timestamp())}.jpg"
            generate_scene_image(t_prompt, t_text, 1280, 720, t_path)
            st.session_state["last_thumb"] = t_path

    if "last_thumb" in st.session_state and os.path.exists(st.session_state["last_thumb"]):
        st.image(st.session_state["last_thumb"], use_container_width=True)
        with open(st.session_state["last_thumb"], "rb") as tf:
            st.download_button("⬇️ Download Thumbnail", data=tf, file_name="thumbnail.jpg", mime="image/jpeg")

# ---------------- TAB 4: SMART UPLOAD SCHEDULER ----------------
with tab4:
    st.subheader("📅 One-Click YouTube Upload & Smart Scheduler")
    st.info(f"⚡ **Recommended Upload Slot ({selected_mode}):** {MODES[selected_mode]['best_time']}")

    if active_channel == "None":
        st.warning("कृपया बाएं साइडबार से अपना YouTube चैनल कनेक्ट करें।")
    else:
        use_generated = st.checkbox("Use Auto-Generated Video from Tab 2", value=("last_video" in st.session_state))
        uploaded_file = None if use_generated else st.file_uploader("Or Upload MP4 File Manually", type=["mp4", "mov"])

        p_data = st.session_state.get("project", {})
        u_title = st.text_input("Video Title", value=(p_data.get("titles", [""])[0] if p_data.get("titles") else ""))
        u_desc = st.text_area("Video Description", value=p_data.get("description", ""))
        u_tags = st.text_input("Video Tags", value=p_data.get("tags", ""))

        pub_choice = st.radio("Publish Setting", ["Private Draft", "Publish Now (Public)", "Schedule for Later"])
        s_date = st.date_input("Schedule Date", datetime.date.today() + datetime.timedelta(days=1))
        s_time = st.time_input("Schedule Time (UTC)", datetime.time(14, 0))

        if st.button("🚀 Upload to YouTube Channel"):
            target_video = st.session_state.get("last_video") if use_generated else None
            if not target_video and uploaded_file:
                os.makedirs("outputs", exist_ok=True)
                target_video = os.path.join("outputs", uploaded_file.name)
                with open(target_video, "wb") as f:
                    f.write(uploaded_file.getbuffer())

            if not target_video or not os.path.exists(target_video):
                st.error("कोई वीडियो फाइल नहीं मिली! पहले Tab 2 में वीडियो बनाएं या फाइल चुनें।")
            else:
                yt = authenticate_youtube_channel(active_channel)
                if yt:
                    status_obj = {"selfDeclaredMadeForKids": False}
                    if pub_choice == "Publish Now (Public)":
                        status_obj["privacyStatus"] = "public"
                    elif pub_choice == "Private Draft":
                        status_obj["privacyStatus"] = "private"
                    else:
                        status_obj["privacyStatus"] = "private"
                        status_obj["publishAt"] = datetime.datetime.combine(s_date, s_time).isoformat() + "Z"

                    body = {
                        "snippet": {
                            "title": u_title[:100],
                            "description": u_desc,
                       
