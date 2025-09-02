import os
import struct
import mimetypes
import uuid
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types


def _project_public_dir() -> str:
    project_root = os.path.dirname(os.path.dirname(__file__))
    public_dir = os.path.join(project_root, "public")
    os.makedirs(public_dir, exist_ok=True)
    return public_dir


def parse_audio_mime_type(mime_type: str) -> dict[str, int | None]:
    """Parse bits per sample and rate from an audio MIME type string.

    Defaults to 16-bit, 24000 Hz if not specified.
    """
    bits_per_sample = 16
    rate = 24000
    parts = [p.strip() for p in (mime_type or "").split(";")]
    for p in parts:
        if p.lower().startswith("rate="):
            try:
                rate = int(p.split("=", 1)[1])
            except Exception:
                pass
        if p.startswith("audio/L"):
            try:
                bits_per_sample = int(p.split("L", 1)[1])
            except Exception:
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    """Wrap raw PCM data in a WAV container using parsed parameters."""
    params = parse_audio_mime_type(mime_type)
    bits_per_sample = int(params.get("bits_per_sample") or 16)
    sample_rate = int(params.get("rate") or 24000)
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,
        1,
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size,
    )
    return header + audio_data


def text_to_speech(text: str, voice_name: str, output_dir: Optional[str] = None):
    """Generate speech audio from text using Gemini TTS (gemini-2.5-flash-preview-tts).

    Inputs: text, voice_name. Saves a file in public/ and returns filename.
    """
    try:
        load_dotenv()
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {"success": False, "message": "Missing GOOGLE_API_KEY in environment.", "filename": None}

        client = genai.Client(api_key=api_key)

        model = "gemini-2.5-flash-preview-tts"
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=text or "")],
            )
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice_name or "")
                )
            ),
        )

        # Stream and collect audio chunks
        audio_chunks: list[bytes] = []
        mime_type: Optional[str] = None
        for chunk in client.models.generate_content_stream(
            model=model, contents=contents, config=generate_content_config
        ):
            if not getattr(chunk, "candidates", None):
                continue
            c0 = chunk.candidates[0]
            if not getattr(c0, "content", None) or not getattr(c0.content, "parts", None):
                continue
            part0 = c0.content.parts[0]
            if getattr(part0, "inline_data", None) and getattr(part0.inline_data, "data", None):
                mime_type = part0.inline_data.mime_type or mime_type
                audio_chunks.append(part0.inline_data.data)

        if not audio_chunks:
            return {"success": False, "message": "No audio data received from model.", "filename": None}

        raw = b"".join(audio_chunks)

        # Decide output extension and payload
        ext = mimetypes.guess_extension(mime_type or "") or ".wav"
        if ext.lower() == ".wav":
            payload = raw if (mime_type and mime_type.lower().startswith("audio/wav")) else convert_to_wav(raw, mime_type or "audio/L16;rate=24000")
        else:
            # If it's not recognizable as WAV, save as given (e.g., .mp3)
            payload = raw

        target_dir = output_dir or _project_public_dir()
        os.makedirs(target_dir, exist_ok=True)
        filename = f"tts_{uuid.uuid4().hex}{ext}"
        out_path = os.path.join(target_dir, filename)
        with open(out_path, "wb") as f:
            f.write(payload)

        return {
            "success": True,
            "message": "Speech synthesized successfully.",
            "filename": filename,
        }
    except Exception as e:
        return {"success": False, "message": f"Error during TTS: {e}", "filename": None}
