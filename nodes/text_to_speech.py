import os
import html
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk


def text_to_speech(text: str, voice_name: str, output_path: str, language: str):
    """
    Generate speech audio from text using Azure Speech with a specified voice.

    Args:
        text: Text to synthesize.
        voice_name: Azure voice name (e.g., "en-US-JennyNeural", "ar-EG-SalmaNeural").
        output_path: WAV file path to write the synthesized audio.

    Returns:
        dict with success, message, and output_file.
    """
    try:
        load_dotenv()
        key = os.getenv("AZURE_SPEECH_KEY_TTS")
        region = os.getenv("AZURE_SPEECH_REGION_TTS")
        if not key or not region:
            return {
                "success": False,
                "message": "Missing AZURE_SPEECH_KEY_TTS or AZURE_SPEECH_REGION_TTS in environment.",
                "output_file": None,
            }

        speech_config = speechsdk.SpeechConfig(subscription=key, region=region)
        # Use a stable PCM format to reduce edge cases with tiny outputs
        try:
            speech_config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
        except Exception:
            # Some SDK versions allow property assignment instead
            try:
                speech_config.speech_synthesis_output_format = (
                    speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
                )
            except Exception:
                pass
        # Prefer explicit voice over language to avoid SDK routing oddities
        if voice_name:
            speech_config.speech_synthesis_voice_name = voice_name
        elif language:
            speech_config.speech_synthesis_language = language

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        # Use a WAV file output stream to force writing to the specified path
        wav_stream = None
        try:
            wav_stream = speechsdk.audio.AudioOutputStream.create_wav_file_output(output_path)
            audio_config = speechsdk.audio.AudioOutputConfig(stream=wav_stream)
        except Exception:
            # Fallback to filename mode if stream-based is unavailable
            audio_config = speechsdk.audio.AudioOutputConfig(filename=output_path)
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=audio_config)

        # For very short inputs (single word or extremely short text), use SSML with an explicit <voice>
        # and a short trailing break to encourage the SDK to emit a proper WAV consistently.
        normalized = (text or "").strip()
        word_count = len(normalized.split())
        use_ssml = (word_count <= 1) or (len(normalized) < 4)
        if use_ssml:
            # Resolve SSML locale and voice.
            def _default_voice_for_lang(lang_code: str) -> str:
                if not lang_code:
                    return "en-US-JennyNeural"
                lc = lang_code.lower()
                if lc.startswith("ar"): return "ar-EG-SalmaNeural"
                if lc.startswith("en"): return "en-US-JennyNeural"
                if lc.startswith("zh"): return "zh-CN-XiaoxiaoNeural"
                if lc.startswith("fr"): return "fr-FR-DeniseNeural"
                if lc.startswith("es"): return "es-ES-ElviraNeural"
                if lc.startswith("de"): return "de-DE-KatjaNeural"
                if lc.startswith("it"): return "it-IT-ElsaNeural"
                if lc.startswith("ja"): return "ja-JP-NanamiNeural"
                if lc.startswith("ko"): return "ko-KR-SunHiNeural"
                if lc.startswith("pt"): return "pt-BR-FranciscaNeural"
                if lc.startswith("ru"): return "ru-RU-DariyaNeural"
                if lc.startswith("tr"): return "tr-TR-EmelNeural"
                return "en-US-JennyNeural"

            # Prefer provided voice; else choose a default for the language; else generic English.
            ssml_voice = voice_name or _default_voice_for_lang(language)
            # Choose SSML language: prefer derived from voice, else provided language, else default.
            ssml_lang = None
            if ssml_voice and "-" in ssml_voice:
                parts = ssml_voice.split("-")
                if len(parts) >= 2:
                    ssml_lang = f"{parts[0]}-{parts[1]}"
            if not ssml_lang:
                ssml_lang = language or "en-US"

            esc_text = html.escape(normalized, quote=True)
            ssml = (
                f"<speak version='1.0' xml:lang='{ssml_lang}'>"
                f"<voice name='{ssml_voice}'>"
                f"<p><s><break time='200ms'/>"  # pre-pause
                f"{esc_text}."
                f"<break time='600ms'/></s></p>"  # post-pause
                f"</voice>"
                f"</speak>"
            )
            result = synthesizer.speak_ssml_async(ssml).get()
        else:
            result = synthesizer.speak_text_async(text).get()

        # Ensure stream is closed to flush bytes to disk (esp. on Windows)
        try:
            if wav_stream and hasattr(wav_stream, "close"):
                wav_stream.close()
        except Exception:
            pass

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            # Helper to check valid WAV size (44 bytes header minimal)
            def _filesize(p: str) -> int:
                try:
                    return os.path.getsize(p)
                except Exception:
                    return 0
            # Helper to read 'data' chunk size in WAV
            def _wav_data_size(p: str) -> int:
                try:
                    with open(p, 'rb') as f:
                        b = f.read()
                    idx = b.find(b'data')
                    if idx == -1 or idx + 8 > len(b):
                        return 0
                    # next 4 bytes little-endian is chunk size
                    import struct
                    return struct.unpack('<I', b[idx+4:idx+8])[0]
                except Exception:
                    return 0

            size = _filesize(output_path)
            data_bytes = _wav_data_size(output_path) if size >= 44 else 0
            if size < 44:
                # Try fallback: write in-memory audio data if available
                audio_bytes = getattr(result, 'audio_data', None)
                if audio_bytes and len(audio_bytes) >= 44:
                    with open(output_path, 'wb') as f:
                        f.write(audio_bytes)
            size = _filesize(output_path)
            data_bytes = _wav_data_size(output_path)

            # If still too small and we used SSML, attempt one retry with longer trailing break
            MIN_DATA_BYTES = 1024  # require at least ~1KB of audio data to avoid near-empty files
            if (size < 44 or data_bytes < MIN_DATA_BYTES) and use_ssml:
                try:
                    esc_text = html.escape(normalized, quote=True)
                    # Reuse the resolved ssml_voice/ssml_lang if available; recompute if not in scope
                    def _default_voice_for_lang(lang_code: str) -> str:
                        if not lang_code:
                            return "en-US-JennyNeural"
                        lc = lang_code.lower()
                        if lc.startswith("ar"): return "ar-EG-SalmaNeural"
                        if lc.startswith("en"): return "en-US-JennyNeural"
                        if lc.startswith("zh"): return "zh-CN-XiaoxiaoNeural"
                        if lc.startswith("fr"): return "fr-FR-DeniseNeural"
                        if lc.startswith("es"): return "es-ES-ElviraNeural"
                        if lc.startswith("de"): return "de-DE-KatjaNeural"
                        if lc.startswith("it"): return "it-IT-ElsaNeural"
                        if lc.startswith("ja"): return "ja-JP-NanamiNeural"
                        if lc.startswith("ko"): return "ko-KR-SunHiNeural"
                        if lc.startswith("pt"): return "pt-BR-FranciscaNeural"
                        if lc.startswith("ru"): return "ru-RU-DariyaNeural"
                        if lc.startswith("tr"): return "tr-TR-EmelNeural"
                        return "en-US-JennyNeural"

                    retry_voice = voice_name or _default_voice_for_lang(language)
                    retry_lang = None
                    if retry_voice and "-" in retry_voice:
                        parts = retry_voice.split("-")
                        if len(parts) >= 2:
                            retry_lang = f"{parts[0]}-{parts[1]}"
                    if not retry_lang:
                        retry_lang = language or "en-US"

                    ssml_retry = (
                        f"<speak version='1.0' xml:lang='{retry_lang}'>"
                        f"<voice name='{retry_voice}'>"
                        f"<p><s><break time='300ms'/>"
                        f"{esc_text}."
                        f"<break time='900ms'/></s></p>"
                        f"</voice>"
                        f"</speak>"
                    )
                    # Recreate a filename-based audio config to avoid stream reuse issues
                    retry_audio_cfg = speechsdk.audio.AudioOutputConfig(filename=output_path)
                    retry_synth = speechsdk.SpeechSynthesizer(speech_config=speech_config, audio_config=retry_audio_cfg)
                    retry_result = retry_synth.speak_ssml_async(ssml_retry).get()
                    if retry_result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                        size = _filesize(output_path)
                        data_bytes = _wav_data_size(output_path) if size >= 44 else 0
                        if size < 44 or data_bytes < MIN_DATA_BYTES:
                            # Final fallback: write in-memory audio if any
                            rb = getattr(retry_result, 'audio_data', None)
                            if rb and len(rb) >= 44:
                                with open(output_path, 'wb') as f:
                                    f.write(rb)
                                size = _filesize(output_path)
                                data_bytes = _wav_data_size(output_path)
                except Exception:
                    pass

            if size >= 44 and data_bytes >= MIN_DATA_BYTES:
                return {
                    "success": True,
                    "message": "Speech synthesized successfully.",
                    "output_file": output_path,
                }

            # Clean up empty file to avoid leaving a 0-byte artifact
            try:
                if os.path.exists(output_path) and _filesize(output_path) == 0:
                    os.remove(output_path)
            except Exception:
                pass

            return {
                "success": False,
                "message": "Synthesis completed but produced empty/invalid audio for very short input. Try a longer text or different voice.",
                "output_file": None,
            }
        elif result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            return {
                "success": False,
                "message": f"Synthesis canceled: {details.reason}. Error: {getattr(details, 'error_details', '')}",
                "output_file": None,
            }
        else:
            return {
                "success": False,
                "message": f"Unexpected result: {result.reason}",
                "output_file": None,
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error during TTS: {str(e)}",
            "output_file": None,
        }
