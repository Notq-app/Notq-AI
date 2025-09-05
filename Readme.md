# notq-ai

A FastAPI service with:

- Speech utilities (level measurement, word-level measurement, Azure Text-to-Speech)
- Speech therapy plan generation using Google Gemini via LangChain
- A simple Streamlit UI to exercise the endpoints

Static files (generated TTS WAVs) are persisted under `public/` and served at `/public`.

## Contents

- Setup (Python + env vars)
- Running the API and Streamlit
- Endpoints and examples
- Docker usage
- Troubleshooting

---

## 1) Setup

### Prerequisites

- Python 3.12
- An Azure Cognitive Services Speech resource (for TTS)
- A Google API key (for Gemini model)

### Environment variables

Create a `.env` file in the project root (or set env vars directly):

```
AZURE_SPEECH_KEY_TTS=your-azure-speech-key
AZURE_SPEECH_REGION_TTS=your-azure-region   # e.g., eastus
GOOGLE_API_KEY=your-google-api-key          # for Gemini via LangChain
# Optional for Streamlit default
API_URL=http://localhost:8000
```

### Install dependencies

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## 2) Run locally

### Start the API

```powershell
python main.py
```

The API listens on `http://localhost:8000` and serves generated audio at `http://localhost:8000/public/...`.

### Start the Streamlit UI

```powershell
streamlit run streamlit.py
```

- In the sidebar, set API base URL (or it reads `API_URL` from env).
- Use the pages to call each endpoint and view results.

---

## 3) Endpoints

Base URL: `http://localhost:8000`

### GET /health

- Purpose: quick service check.
- Response:

```json
{ "status": "API is running" }
```

### POST /level_measurement

- Content-Type: multipart/form-data
- Fields:
  - `audio_file`: audio to analyze (wav/mp3/…)
  - `reference_text`: the transcript or phrase to evaluate
  - `language`: locale string (default: `en-US`)
- Returns: JSON with the measurement results.

Example (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/level_measurement `
  -Form @{ audio_file=Get-Item .\sample.wav; reference_text="hello world"; language="en-US" }
```

### POST /text_to_speach

- Content-Type: application/x-www-form-urlencoded (form fields)
- Fields:
  - `text` (required)
  - `voice_name` (required) e.g., `en-US-AndrewMultilingualNeural`, `en-US-JennyNeural`, `ar-EG-SalmaNeural`
  - `language` (default `en-US`)
- Behavior:
  - Saves a WAV under `public/tts_<uuid>.wav`
  - Returns a direct `download_url`

Example (PowerShell):

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/text_to_speach `
  -Body @{ text="Hello"; voice_name="en-US-AndrewMultilingualNeural"; language="en-US" } `
  -ContentType "application/x-www-form-urlencoded"
```

Response:

```json
{
  "success": true,
  "message": "Speech synthesized successfully.",
  "filename": "tts_<uuid>.wav",
  "download_url": "http://localhost:8000/public/tts_<uuid>.wav"
}
```

### POST /generate_speech_plan

- Content-Type: application/x-www-form-urlencoded (form fields)
- Fields:
  - `child_age` (required): Child's age (2-8 years)
  - `delay_level` (required): Speech delay level: "slight delay", "medium delay", or "severe delay"
  - `language` (optional): Primary language (default: "English")
  - `daily_time_minutes` (optional): Available practice time per day in minutes (default: 15)
  - `plan_duration_weeks` (optional): Plan duration in weeks 1-12 (default: 4)
  - `words_child_can_speak` (optional): Words the child can already speak (comma-separated)
  - `additional_info` (optional): Additional information about the child
- Returns: JSON with structured speech therapy plan including weekly breakdown and daily word lists

Notes:

- For very short inputs (one word), the service uses SSML and extra pauses to avoid empty WAVs.
- Files remain in `public/`; `.dockerignore` is configured to skip committing them.

---

## 4) Streamlit testing

Run the UI and use the sidebar to switch between pages:

- Health
- Level Measurement
- Text to Speech
- Generate Speech Plan

It posts to the API base URL shown in the sidebar (reads `API_URL` by default). TTS results show a download link and inline audio playback.

---

## 5) Docker

A minimal, production-friendly image is provided.

Build:

```powershell
docker build -t notq-ai .
```

Run:

```powershell
docker run --rm -p 8000:8000 `
  -e AZURE_SPEECH_KEY_TTS=$Env:AZURE_SPEECH_KEY_TTS `
  -e AZURE_SPEECH_REGION_TTS=$Env:AZURE_SPEECH_REGION_TTS `
  -e GOOGLE_API_KEY=$Env:GOOGLE_API_KEY `
  notq-ai
```

Then open `http://localhost:8000/health` or run Streamlit separately pointing to that API URL.

---

## 6) Troubleshooting

- Missing Azure/Google keys
  - Ensure `AZURE_SPEECH_KEY_TTS`, `AZURE_SPEECH_REGION_TTS`, and `GOOGLE_API_KEY` are set.
- Short TTS inputs produce empty audio
  - The service adds SSML breaks and retries. If still empty, try a longer phrase or a different voice.
- Permissions writing to `public/`
  - The API creates `public/` automatically. Check file permissions if running in restricted environments.
- CORS/Fetch errors in UI
  - The Streamlit app fetches audio via the `download_url`. If hosted separately, ensure the URL is reachable.

---

## 7) Project structure

```
notq-ai/
  main.py                 # FastAPI app and endpoints, /public static mount
  streamlit.py            # Streamlit UI to test endpoints
  requirements.txt        # Python dependencies
  nodes/
    level_measurement.py  # Audio/text analysis (reference level)
    text_to_speech.py     # Azure TTS with robust handling for short texts
    generate_plan.py      # LangChain + Gemini speech therapy plan generator
  public/                 # Generated TTS WAVs (runtime)
```

---

## 8) Notes

- Uses `langchain-google-genai` with model `gemini-2.5-flash`.
- TTS formats output as `Riff16Khz16BitMonoPcm` WAV files.
- Streamlit voice dropdown includes common example voices; pass any supported Azure voice name.
