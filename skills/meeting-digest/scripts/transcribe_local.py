"""Create a timestamped raw transcript for later speaker alignment."""
import argparse
import json
from pathlib import Path


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--model', default='small')
    p.add_argument('--language')
    p.add_argument('--device', default='cpu')
    p.add_argument('--compute-type', default='int8')
    a = p.parse_args()
    targets = [a.output / 'transcript_raw.json', a.output / 'transcript_raw.md']
    if any(t.exists() for t in targets):
        p.error('Transcript exists; choose a new output directory.')
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        p.error('Install faster-whisper in this Python environment first.')
    model = WhisperModel(a.model, device=a.device, compute_type=a.compute_type)
    segments, info = model.transcribe(str(a.audio), language=a.language, word_timestamps=True)
    rows = [dict(start=s.start, end=s.end, text=s.text.strip(),
                 words=[dict(start=w.start, end=w.end, text=w.word)
                        for w in (s.words or []) if w.start is not None and w.end is not None])
            for s in segments]
    result = dict(source=str(a.audio.resolve()), language=info.language,
                  backend=f'faster-whisper/{a.model}', segments=rows)
    a.output.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    targets[1].write_text('# Transcript\n\n' + '\n\n'.join(
        f'[{stamp(s["start"])}–{stamp(s["end"])}] {s["text"]}' for s in rows), encoding='utf-8')
    print(targets[0])


if __name__ == '__main__':
    main()
