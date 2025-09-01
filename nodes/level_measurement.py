import os
import time
import string
import difflib
import json
import statistics
from dotenv import load_dotenv
import azure.cognitiveservices.speech as speechsdk

def level_measurement(audio_file: str, reference_text: str, language: str = 'en-US'):
    """
    Performs continuous pronunciation assessment asynchronously with input from an audio file.
    Returns a dictionary with all measurement results.
    """
    load_dotenv()
    subscription_key = os.getenv('AZURE_SPEECH_KEY_LEVEL_MEASUREMENT')
    service_region = os.getenv('AZURE_SPEECH_REGION_LEVEL_MEASUREMENT')

    speech_config = speechsdk.SpeechConfig(subscription=subscription_key, region=service_region)
    audio_config = speechsdk.audio.AudioConfig(filename=audio_file)

    enable_miscue = True
    enable_prosody_assessment = True
    pronunciation_config = speechsdk.PronunciationAssessmentConfig(
        reference_text=reference_text,
        grading_system=speechsdk.PronunciationAssessmentGradingSystem.HundredMark,
        granularity=speechsdk.PronunciationAssessmentGranularity.Phoneme,
        enable_miscue=enable_miscue)
    if enable_prosody_assessment:
        pronunciation_config.enable_prosody_assessment()

    speech_recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, language=language, audio_config=audio_config)
    pronunciation_config.apply_to(speech_recognizer)

    done = False
    recognized_words = []
    fluency_scores = []
    prosody_scores = []
    durations = []  # per recognized segment total word duration (ticks)
    recognized_segments = []  # store NBest[0] per segment for deep analysis
    recognized_results_raw = []  # full JSON results per segment
    segment_summaries = []  # summary per segment: text, confidence, scores, times
    transcripts_display = []
    transcripts_lexical = []
    recognized_json_words = []  # flattened words for timeline

    def stop_cb(evt: speechsdk.SessionEventArgs):
        nonlocal done
        done = True

    def recognized(evt: speechsdk.SpeechRecognitionEventArgs):
        pronunciation_result = speechsdk.PronunciationAssessmentResult(evt.result)
        nonlocal recognized_words, fluency_scores, durations, prosody_scores
        recognized_words += pronunciation_result.words

        # Align one duration per recognized result; default to 0 when not present
        dur = 0
        try:
            json_result = evt.result.properties.get(speechsdk.PropertyId.SpeechServiceResponse_JsonResult)
            if json_result:
                jo = json.loads(json_result)
                recognized_results_raw.append(jo)
                nbest_list = jo.get('NBest', [])
                nb = nbest_list[0] if nbest_list else {}
                words = nb.get('Words', [])
                # Persist segment and words for post-analysis
                recognized_segments.append(nb)
                recognized_json_words.extend(words)
                dur = sum(int(w.get('Duration', 0)) for w in words if isinstance(w.get('Duration', 0), (int, str)))

                # Segment summary
                seg_text_display = nb.get('Display') or nb.get('Lexical') or nb.get('Text')
                seg_text_lexical = nb.get('Lexical') or nb.get('Text') or seg_text_display
                transcripts_display.append(seg_text_display or '')
                transcripts_lexical.append(seg_text_lexical or '')
                seg_conf = nb.get('Confidence')
                seg_flu = pronunciation_result.fluency_score if pronunciation_result.fluency_score is not None else None
                seg_pros = pronunciation_result.prosody_score if pronunciation_result.prosody_score is not None else None
                # Approx segment times
                seg_offset = min((int(w.get('Offset', 0)) for w in words), default=0)
                seg_end = max(((int(w.get('Offset', 0)) + int(w.get('Duration', 0))) for w in words), default=0)
                segment_summaries.append({
                    'display': seg_text_display,
                    'lexical': seg_text_lexical,
                    'confidence': seg_conf,
                    'fluency_score': seg_flu,
                    'prosody_score': seg_pros,
                    'offset_sec': seg_offset / 10_000_000 if seg_offset else 0.0,
                    'end_sec': seg_end / 10_000_000 if seg_end else 0.0,
                    'duration_sec': ((seg_end - seg_offset) / 10_000_000) if (seg_end and seg_offset and seg_end >= seg_offset) else (dur / 10_000_000),
                    'alternatives': [
                        {
                            'display': alt.get('Display') or alt.get('Lexical') or alt.get('Text'),
                            'lexical': alt.get('Lexical') or alt.get('Text'),
                            'confidence': alt.get('Confidence'),
                        }
                        for alt in nbest_list[:5]
                    ] if nbest_list else []
                })
        except Exception:
            dur = 0
        durations.append(dur)

        # Guard None values for scores; ensure list lengths match durations
        fs = pronunciation_result.fluency_score if pronunciation_result.fluency_score is not None else 0.0
        fluency_scores.append(fs)
        if pronunciation_result.prosody_score is not None:
            prosody_scores.append(pronunciation_result.prosody_score)

    speech_recognizer.recognized.connect(recognized)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(stop_cb)

    try:
        speech_recognizer.start_continuous_recognition()
        while not done:
            time.sleep(.2)
        speech_recognizer.stop_continuous_recognition()
    finally:
        # Best-effort cleanup to release file handles on Windows
        try:
            speech_recognizer.recognized.disconnect_all()
        except Exception:
            pass
        try:
            speech_recognizer.session_stopped.disconnect_all()
        except Exception:
            pass
        try:
            speech_recognizer.canceled.disconnect_all()
        except Exception:
            pass
        # Drop references to encourage GC to close underlying handles
        speech_recognizer = None
        audio_config = None

    if language == 'zh-CN':
        import jieba
        import zhon.hanzi
        jieba.suggest_freq([x.word for x in recognized_words], True)
        reference_words = [w for w in jieba.cut(reference_text) if w not in zhon.hanzi.punctuation]
    else:
        reference_words = [w.strip(string.punctuation) for w in reference_text.lower().split()]

    if enable_miscue:
        diff = difflib.SequenceMatcher(None, reference_words, [x.word.lower() for x in recognized_words])
        final_words = []
        for tag, i1, i2, j1, j2 in diff.get_opcodes():
            if tag in ['insert', 'replace']:
                for word in recognized_words[j1:j2]:
                    if word.error_type == 'None':
                        word._error_type = 'Insertion'
                    final_words.append(word)
            if tag in ['delete', 'replace']:
                for word_text in reference_words[i1:i2]:
                    word = speechsdk.PronunciationAssessmentWordResult({
                        'Word': word_text,
                        'PronunciationAssessment': {
                            'ErrorType': 'Omission',
                        }
                    })
                    final_words.append(word)
            if tag == 'equal':
                final_words += recognized_words[j1:j2]
    else:
        final_words = recognized_words

    final_accuracy_scores = [word.accuracy_score for word in final_words if word.error_type != 'Insertion']
    accuracy_score = sum(final_accuracy_scores) / len(final_accuracy_scores) if final_accuracy_scores else 0
    fluency_score = sum(x * y for (x, y) in zip(fluency_scores, durations)) / sum(durations) if durations and sum(durations) > 0 else 0
    completeness_score = len([w for w in recognized_words if w.error_type == "None"]) / len(reference_words) * 100 if reference_words else 0
    completeness_score = completeness_score if completeness_score <= 100 else 100
    numeric_prosody = [ps for ps in prosody_scores if isinstance(ps, (int, float))]
    prosody_score = sum(numeric_prosody) / len(numeric_prosody) if numeric_prosody else 0

    # Re-normalize weights if prosody is unavailable (keeps response fields but avoids unfairly penalizing)
    weights = {"accuracy": 0.4, "prosody": 0.2, "fluency": 0.2, "completeness": 0.2}
    components = {
        "accuracy": accuracy_score,
        "prosody": prosody_score if numeric_prosody else None,
        "fluency": fluency_score,
        "completeness": completeness_score,
    }
    active = {k: v for k, v in components.items() if v is not None}
    total_w = sum(weights[k] for k in active.keys())
    pron_score = sum(active[k] * (weights[k] / total_w) for k in active.keys()) if total_w > 0 else 0

    word_results = [
        {
            'word': word.word,
            'accuracy_score': word.accuracy_score,
            'error_type': word.error_type
        }
        for word in final_words
    ]

    # Compute additional analytics
    insertion_count = len([w for w in final_words if w.error_type == 'Insertion'])
    omission_count = len([w for w in final_words if w.error_type == 'Omission'])
    mispronunciation_count = len([w for w in final_words if w.error_type == 'Mispronunciation'])
    correct_count = len([w for w in final_words if w.error_type == 'None'])
    total_ref = len(reference_words)
    wer = ((mispronunciation_count + omission_count + insertion_count) / total_ref) * 100 if total_ref else 0

    # Build per-word timeline using offsets/durations from JSON when available
    TICKS_PER_SECOND = 10_000_000
    def to_sec(ticks):
        try:
            return int(ticks) / TICKS_PER_SECOND
        except Exception:
            return 0.0

    timeline = []
    for w in recognized_json_words:
        pa = (w.get('PronunciationAssessment') or {}) if isinstance(w, dict) else {}
        timeline.append({
            'word': w.get('Word'),
            'offset_sec': to_sec(w.get('Offset', 0)),
            'duration_sec': to_sec(w.get('Duration', 0)),
            'end_sec': to_sec(int(w.get('Offset', 0)) + int(w.get('Duration', 0)) if str(w.get('Offset', '0')).isdigit() and str(w.get('Duration', '0')).isdigit() else 0),
            'accuracy_score': pa.get('AccuracyScore'),
            'error_type': pa.get('ErrorType'),
            # Include syllables/phonemes raw details when present (shape varies by locale)
            'syllables': w.get('Syllables'),
        })

    if timeline:
        span_start = min(item['offset_sec'] for item in timeline)
        span_end = max(item['end_sec'] for item in timeline)
        span_duration_sec = max(span_end - span_start, 0.0)
    else:
        span_duration_sec = 0.0

    speech_time_sec = sum(to_sec(d) for d in durations)
    words_count = len([w for w in recognized_json_words if isinstance(w, dict)])
    wpm_span = (words_count / span_duration_sec * 60.0) if span_duration_sec > 0 else 0.0
    wpm_articulation = (words_count / speech_time_sec * 60.0) if speech_time_sec > 0 else 0.0

    # Detect silence segments between timeline words
    silences = []
    if len(timeline) >= 2:
        timeline_sorted = sorted(timeline, key=lambda x: x['offset_sec'])
        for prev, nxt in zip(timeline_sorted, timeline_sorted[1:]):
            gap = max(nxt['offset_sec'] - prev['end_sec'], 0.0)
            if gap > 0:
                silences.append({
                    'start_sec': prev['end_sec'],
                    'end_sec': nxt['offset_sec'],
                    'duration_sec': gap,
                })

    # Aggregate per unique word (case-insensitive)
    per_word = {}
    for item in timeline:
        key = (item['word'] or '').lower()
        if not key:
            continue
        agg = per_word.setdefault(key, {
            'occurrences': 0,
            'avg_accuracy': None,
            'min_accuracy': None,
            'max_accuracy': None,
            'total_duration_sec': 0.0,
        })
        acc = item.get('accuracy_score')
        agg['occurrences'] += 1
        agg['total_duration_sec'] += item.get('duration_sec') or 0.0
        if isinstance(acc, (int, float)):
            if agg['avg_accuracy'] is None:
                agg['avg_accuracy'] = acc
                agg['min_accuracy'] = acc
                agg['max_accuracy'] = acc
            else:
                # running average
                agg['avg_accuracy'] = (agg['avg_accuracy'] * (agg['occurrences'] - 1) + acc) / agg['occurrences']
                agg['min_accuracy'] = min(agg['min_accuracy'], acc)
                agg['max_accuracy'] = max(agg['max_accuracy'], acc)

    # Accuracy distribution buckets
    def bucket(score):
        try:
            s = float(score)
        except Exception:
            return 'unknown'
        if s < 60:
            return '<60'
        if s < 80:
            return '60-79'
        if s < 90:
            return '80-89'
        if s < 100:
            return '90-99'
        return '100'

    acc_buckets = {}
    for w in timeline:
        b = bucket(w.get('accuracy_score'))
        acc_buckets[b] = acc_buckets.get(b, 0) + 1

    # Compute an overall delay score using fluency, completeness, and silence
    total_silence_sec = sum(s.get('duration_sec', 0.0) for s in silences) if 'silences' in locals() else 0.0
    silence_ratio = (total_silence_sec / span_duration_sec) if span_duration_sec > 0 else 0.0
    fluency_norm = max(0.0, min(1.0, fluency_score / 100.0))
    completeness_norm = max(0.0, min(1.0, completeness_score / 100.0))
    # Composite delay index: higher means more delay
    delay_index = 0.5 * (1.0 - fluency_norm) + 0.3 * silence_ratio + 0.2 * (1.0 - completeness_norm)

    levels_map = {
        0: 'natural',
        1: 'slight delay',
        2: 'Medium delay',
        3: 'severe delay',
    }
    if delay_index < 0.20:
        level_code = 0
    elif delay_index < 0.35:
        level_code = 1
    elif delay_index < 0.55:
        level_code = 2
    else:
        level_code = 3

    # Final 1-10 score (higher is better). Combine inverse delay with accuracy and fluency.
    # Clamp in [1,10] and round to nearest int.
    inv_delay = max(0.0, min(1.0, 1.0 - delay_index))
    acc_norm = max(0.0, min(1.0, accuracy_score / 100.0))
    flu_norm = max(0.0, min(1.0, fluency_score / 100.0))
    quality = 0.5 * inv_delay + 0.25 * acc_norm + 0.25 * flu_norm
    score = int(round(1 + (max(0.0, min(1.0, quality)) * 9)))

    return {
        'level_measured': level_code,
        'levels': levels_map,
        'score': score,
        # Backward-compatible top-level scores
        'paragraph_pronunciation_score': pron_score,
        'accuracy_score': accuracy_score,
        'completeness_score': completeness_score,
        'fluency_score': fluency_score,
        'prosody_score': prosody_score,
        'words': word_results,

        # New detailed analytics
        'analytics': {
            'word_error_rate_percent': wer,
            'counts': {
                'reference_word_count': total_ref,
                'recognized_word_count': len(recognized_words),
                'correct': correct_count,
                'insertions': insertion_count,
                'omissions': omission_count,
                'mispronunciations': mispronunciation_count,
            },
            'speaking_rates': {
                'wpm_overall_span': wpm_span,
                'wpm_articulation_time': wpm_articulation,
                'total_span_duration_sec': span_duration_sec,
                'total_articulation_time_sec': speech_time_sec,
            },
            'accuracy_distribution': acc_buckets,
            'timeline': timeline,
            'silences': silences,
            'per_word': per_word,
            'transcripts': {
                'display': transcripts_display,
                'lexical': transcripts_lexical,
            },
            'segments': recognized_segments,
            'segment_summaries': segment_summaries,
            'raw': {
                'results': recognized_results_raw,
            },
            'summary': {
                'timeline_word_count': words_count,
                'timeline_span_sec': span_duration_sec,
                'avg_word_duration_sec': (speech_time_sec / words_count) if words_count else 0.0,
                'median_word_duration_sec': (statistics.median([w.get('duration_sec') or 0.0 for w in timeline]) if timeline else 0.0),
            }
        }
    }
