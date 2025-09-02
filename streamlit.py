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
    "Word Level Measurement",
    "Text to Speech",
    "Generate Plan",
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

# Word Level Measurement Page
elif page == "Word Level Measurement":
    st.title("/level_measurement")
    st.write("Upload an audio file, enter the reference text and language.")
    audio = st.file_uploader("Audio file (wav recommended)", type=["wav", "mp3", "m4a", "ogg", "flac", "webm"], key="wlm_audio")
    reference_text = st.text_area("Reference Text", height=120, key="wlm_text")
    language = st.text_input("Language (locale)", value="en-US", key="wlm_lang")

    if st.button("Measure Word-Level"):
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

# Generate Plan Page
elif page == "Generate Plan":
    st.title("/generate_plan")
    st.write("Provide the system prompt, context, objective, optional constraints (comma-separated), and an optional steps hint.")

    # Full-width inputs
    system_prompt = st.text_area(
        "System Prompt",
        height=300,
        placeholder="e.g., You are a senior planning assistant. Produce a clear, actionable plan.",
    )
    context_text = st.text_area(
        "Context (required)",
        height=300,
        placeholder="Paste any background information, requirements, and details to ground the plan...",
    )
    objective = st.text_input(
        "Objective (required)",
        value="",
        help="What is the plan trying to achieve?",
    )
    steps_hint = st.number_input(
        "Steps hint (optional)",
        min_value=0,
        step=1,
        value=0,
        help="Suggest an approximate number of steps. Leave 0 to omit.",
    )
    constraints_text = st.text_area(
        "Constraints (optional, comma-separated)",
        height=120,
        placeholder="budget <= $10k, delivery in 2 weeks, use Python 3.12",
    )

    if st.button("Generate Plan"):
        if not system_prompt.strip():
            st.warning("Please provide the system prompt.")
        elif not context_text.strip():
            st.warning("Please provide the context.")
        elif not objective.strip():
            st.warning("Please provide the objective.")
        else:
            data = {
                "system_prompt": system_prompt,
                "context": context_text,
                "objective": objective,
            }
            # Only include optional fields if provided/valid
            if constraints_text.strip():
                data["constraints"] = constraints_text
            if isinstance(steps_hint, (int, float)) and int(steps_hint) > 0:
                data["steps_hint"] = int(steps_hint)

            with st.spinner("Requesting plan..."):
                resp = post_form(urljoin(api_url + "/", "generate_plan"), data)

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
                        st.subheader("Plan Preview")
                        if plan.get("objective"):
                            st.markdown(f"**Objective:** {plan['objective']}")
                        # Optional lists
                        for label in [
                            ("Assumptions", "assumptions"),
                            ("Constraints", "constraints"),
                            ("Milestones", "milestones"),
                            ("Risks", "risks"),
                            ("Mitigations", "mitigations"),
                            ("Metrics", "metrics"),
                        ]:
                            title, key = label
                            items = plan.get(key) or []
                            if isinstance(items, list) and items:
                                with st.expander(title, expanded=False):
                                    for i, it in enumerate(items, 1):
                                        st.markdown(f"{i}. {it}")
                        # Steps table-like view
                        steps = plan.get("steps") or []
                        if isinstance(steps, list) and steps:
                            st.subheader("Steps")
                            for step in steps:
                                with st.expander(f"{step.get('id', '?')}. {step.get('title', '')}", expanded=False):
                                    st.markdown(f"**Owner:** {step.get('owner') or '-'}")
                                    st.markdown(f"**Duration:** {step.get('duration') or '-'}")
                                    deps = step.get('dependencies') or []
                                    st.markdown(f"**Dependencies:** {', '.join(map(str, deps)) if deps else '-'}")
                                    st.write(step.get('description') or '')
                        # Footer
                        if plan.get("timeline"):
                            st.markdown(f"**Timeline:** {plan['timeline']}")
                        if plan.get("notes"):
                            st.markdown(f"**Notes:** {plan['notes']}")
