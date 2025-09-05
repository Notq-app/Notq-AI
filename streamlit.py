import os
import io
import json
from urllib.parse import urljoin

import streamlit as st
import requests
from dotenv import load_dotenv

# Load environment variables (expects API_URL in .env or environment)
load_dotenv()
DEFAULT_API_URL = os.getenv("API_URL", "https://notq-python-adb7dsexamdkh0gt.germanywestcentral-01.azurewebsites.net").rstrip("/")

# Voice options for Gemini TTS
VOICE_OPTIONS = [
    "zephyr",
    "puck",
    "charon",
    "kore",
    "fenrir",
    "leda",
    "orus",
    "aoede",
    "callirrhoe",
    "autonoe",
    "enceladus",
    "iapetus",
    "umbriel",
    "algieba",
    "despina",
    "erinome",
    "algenib",
    "rasalgethi",
    "laomedeia",
    "achernar",
    "alnilam",
    "schedar",
    "gacrux",
    "pulcherrima",
    "achird",
    "zubenelgenubi",
]

st.set_page_config(page_title="notq-ai API Tester", layout="wide")

# Sidebar: API base URL selection
st.sidebar.header("Settings")
api_url = st.sidebar.text_input("API base URL", value=DEFAULT_API_URL, help="Example: https://notq-python-adb7dsexamdkh0gt.germanywestcentral-01.azurewebsites.net")
if not api_url:
    st.sidebar.warning("API base URL is required. Using default https://notq-python-adb7dsexamdkh0gt.germanywestcentral-01.azurewebsites.net")
    api_url = "https://notq-python-adb7dsexamdkh0gt.germanywestcentral-01.azurewebsites.net"
api_url = api_url.rstrip("/")

st.sidebar.markdown("---")
page = st.sidebar.radio("Endpoints", [
    "Health",
    "Level Measurement",
    "Text to Speech",
    "Generate Speech Plan",
])

# Helper: POST multipart/form-data with file

def post_multipart(url: str, files: dict, data: dict):
    try:
        resp = requests.post(url, files=files, data=data, timeout=120)
        return resp
    except Exception as e:
        return None

# Helper: POST form data

def post_form(url: str, data: dict):
    try:
        resp = requests.post(url, data=data, timeout=120)
        return resp
    except Exception:
        return None

# Health Page
if page == "Health":
    st.title("/health")
    st.write("Quick check that the FastAPI service is up.")
    if st.button("Check Health"):
        try:
            r = requests.get(urljoin(api_url + "/", "health"), timeout=15)
            st.write("Status:", r.status_code)
            try:
                st.json(r.json())
            except Exception:
                st.text(r.text)
        except Exception as e:
            st.error(f"Request failed: {e}")

# Level Measurement Page
elif page == "Level Measurement":
    st.title("/level_measurement")
    st.write("Upload an audio file, enter the reference text and language.")
    audio = st.file_uploader("Audio file (wav recommended)", type=["wav", "mp3", "m4a", "ogg", "flac", "webm"])
    reference_text = st.text_area("Reference Text", height=120)
    language = st.text_input("Language (locale)", value="en-US")

    if st.button("Measure Level"):
        if not audio or not reference_text.strip():
            st.warning("Please provide an audio file and reference text.")
        else:
            files = {
                "audio_file": (audio.name, audio.getvalue(), audio.type or "application/octet-stream"),
            }
            data = {
                "reference_text": reference_text,
                "language": language,
            }
            with st.spinner("Submitting request..."):
                resp = post_multipart(urljoin(api_url + "/", "level_measurement"), files, data)
            if not resp:
                st.error("Request failed (network error).")
            else:
                st.write("Status:", resp.status_code)
                try:
                    st.json(resp.json())
                except Exception:
                    st.text(resp.text)

# Text to Speech Page
elif page == "Text to Speech":
    st.title("/text_to_speach")
    st.write("Enter text and choose a voice. The generated audio will appear below.")

    # Full-width inputs
    text = st.text_area("Text", height=120, placeholder="Type a short sentence or a word...")
    voice_name = st.selectbox(
        "Voice",
        options=VOICE_OPTIONS,
        index=0,
        help="Select a Gemini TTS prebuilt voice. Default is zephyr.",
    )

    if st.button("Synthesize"):
        if not text.strip():
            st.warning("Please enter some text.")
        else:
            data = {
                "text": text,
                "voice_name": voice_name,
            }
            with st.spinner("Calling TTS..."):
                resp = post_form(urljoin(api_url + "/", "text_to_speach"), data)
            if not resp:
                st.error("Request failed (network error).")
            else:
                st.write("Status:", resp.status_code)
                try:
                    payload = resp.json()
                except Exception:
                    payload = None

                if not payload:
                    st.text(resp.text)
                else:
                    st.json(payload)
                    if payload.get("success"):
                        # Build absolute URL if needed
                        download_url = payload.get("download_url") or ""
                        if download_url.startswith("/"):
                            download_url = api_url + download_url

                        st.markdown(f"[Download audio]({download_url})")
                        # Fetch audio bytes for inline playback to avoid CORS issues
                        try:
                            r2 = requests.get(download_url, timeout=60)
                            if r2.ok:
                                # Try to infer format from file extension
                                fmt = None
                                if "." in download_url:
                                    ext = download_url.rsplit(".", 1)[-1].lower()
                                    if ext in ("wav", "mp3", "ogg", "webm", "m4a"):
                                        fmt = f"audio/{'x-wav' if ext=='wav' else ext}"
                                st.audio(r2.content, format=fmt)
                            else:
                                st.info("Could not fetch audio for inline play; use the download link above.")
                        except Exception:
                            st.info("Could not fetch audio for inline play; use the download link above.")

# Generate Speech Plan Page
elif page == "Generate Speech Plan":
    st.title("/generate_speech_plan")
    st.write("Generate a structured speech therapy plan for children with speech delays.")

    # Create two columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        child_age = st.number_input(
            "Child's Age (2-8 years)",
            min_value=2,
            max_value=8,
            value=3,
            step=1,
            help="Age of the child in years"
        )
        
        delay_level = st.selectbox(
            "Speech Delay Level",
            options=["slight delay", "medium delay", "severe delay"],
            index=0,
            help="Select the level of speech delay"
        )
        
        language = st.text_input(
            "Primary Language",
            value="English",
            help="Primary language for the therapy plan"
        )
        
        daily_time_minutes = st.number_input(
            "Daily Practice Time (minutes)",
            min_value=5,
            max_value=60,
            value=15,
            step=5,
            help="Available practice time per day in minutes"
        )
    
    with col2:
        plan_duration_weeks = st.number_input(
            "Plan Duration (weeks)",
            min_value=1,
            max_value=12,
            value=4,
            step=1,
            help="Duration of the therapy plan in weeks"
        )
        
        words_child_can_speak = st.text_area(
            "Words Child Can Already Speak",
            height=100,
            placeholder="mama,dada,ball,more (comma-separated)",
            help="List words the child can already speak, separated by commas"
        )
        
        additional_info = st.text_area(
            "Additional Information",
            height=100,
            placeholder="Any additional information about the child...",
            help="Additional context about the child's condition or preferences"
        )

    if st.button("Generate Speech Therapy Plan", type="primary"):
        # Validate inputs
        if child_age < 2 or child_age > 8:
            st.error("Child age must be between 2 and 8 years")
        elif delay_level not in ["slight delay", "medium delay", "severe delay"]:
            st.error("Please select a valid delay level")
        elif plan_duration_weeks < 1 or plan_duration_weeks > 12:
            st.error("Plan duration must be between 1 and 12 weeks")
        else:
            data = {
                "child_age": child_age,
                "delay_level": delay_level,
                "language": language,
                "daily_time_minutes": daily_time_minutes,
                "plan_duration_weeks": plan_duration_weeks,
                "words_child_can_speak": words_child_can_speak.strip(),
                "additional_info": additional_info.strip()
            }
            
            with st.spinner("Generating speech therapy plan..."):
                resp = post_form(urljoin(api_url + "/", "generate_speech_plan"), data)
            
            if not resp:
                st.error("Request failed (network error).")
            else:
                st.write("Status:", resp.status_code)
                try:
                    payload = resp.json()
                except Exception:
                    payload = None

                if not payload:
                    st.text(resp.text)
                else:
                    st.json(payload)
                    if payload.get("success") and isinstance(payload.get("plan"), dict):
                        plan = payload["plan"]
                        st.markdown("---")
                        st.subheader("Speech Therapy Plan Preview")
                        
                        # Display plan summary
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Child Age", f"{plan.get('child_age', 'N/A')} years")
                        with col2:
                            st.metric("Delay Level", plan.get('delay_level', 'N/A').title())
                        with col3:
                            st.metric("Duration", f"{plan.get('plan_duration_weeks', 'N/A')} weeks")
                        
                        # Display weekly plans
                        weekly_plans = plan.get("weekly_plans", [])
                        if isinstance(weekly_plans, list) and weekly_plans:
                            st.subheader("Weekly Breakdown")
                            for week_plan in weekly_plans:
                                week_num = week_plan.get("week", "?")
                                focus_area = week_plan.get("focus_area", "")
                                weekly_goal = week_plan.get("weekly_goal", "")
                                
                                with st.expander(f"Week {week_num}: {focus_area}", expanded=False):
                                    if weekly_goal:
                                        st.markdown(f"**Goal:** {weekly_goal}")
                                    
                                    daily_plans = week_plan.get("daily_plans", [])
                                    if isinstance(daily_plans, list) and daily_plans:
                                        st.markdown("**Daily Practice Words:**")
                                        for day_plan in daily_plans:
                                            day_num = day_plan.get("day", "?")
                                            words = day_plan.get("words", [])
                                            notes = day_plan.get("notes", "")
                                            
                                            words_str = ", ".join(words) if isinstance(words, list) else str(words)
                                            st.markdown(f"**Day {day_num}:** {words_str}")
                                            if notes:
                                                st.markdown(f"*Notes: {notes}*")
