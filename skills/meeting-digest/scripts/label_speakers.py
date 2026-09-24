"""Align timed transcript words with speaker turns; mark ambiguous words unknown."""
import argparse
import json
import math
from pathlib import Path


def stamp(seconds):
    ms = round(seconds * 1000)
    return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02}.{ms % 1000:03}'


def validate_interval(row):
    start, end = row['start'], row['end']
    if not all(isinstance(x, (int, float)) and math.isfinite(x) for x in (start, end)) or start < 0 or end < start:
        raise ValueError(f'Invalid time interval: {row}')


def speaker_for(word, turns):
    overlap = {}
    duration = max(word['end'] - word['start'], .001)
    for turn in turns:
        shared = max(0.0, min(word['end'], turn['end']) - max(word['start'], turn['start']))
        if shared:
            key = turn['source_speaker']
            overlap[key] = overlap.get(key, 0.0) + shared
    if not overlap:
        return None
    ranked = sorted(overlap.items(), key=lambda x: x[1], reverse=True)
    if ranked[0][1] < .5 * duration:
        return None
    if len(ranked) > 1 and ranked[1][1] >= .5 * ranked[0][1]:
        return None
    return ranked[0][0]


def label(raw, diarization):
    turns = diarization['turns']
    for turn in turns:
        validate_interval(turn)
    turns = sorted(turns, key=lambda t: (t['start'], t['end']))
    words = []
    for segment in raw['segments']:
        validate_interval(segment)
        if not segment.get('words'):
            raise ValueError('Word timestamps are required for reliable speaker alignment.')
        for word in segment['words']:
            validate_interval(word)
            words.append(word)
    words.sort(key=lambda w: (w['start'], w['end']))
    names = {}
    result = []
    for word in words:
        source = speaker_for(word, turns)
        if source is not None and source not in names:
            names[source] = f'Speaker {len(names) + 1}'
        speaker = names.get(source)
        if result and result[-1]['speaker'] == speaker and word['start'] - result[-1]['end'] <= 1.5:
            result[-1]['end'] = max(result[-1]['end'], word['end'])
            result[-1]['text'] += word['text']
        else:
            result.append(dict(start=word['start'], end=word['end'],
                               speaker=speaker, text=word['text'].lstrip()))
    return dict(source=raw['source'], language=raw.get('language'),
                backend=f'{raw["backend"]} + {diarization["backend"]}',
                speakers=names, segments=result,
                note='Null speaker means no reliable match or overlapping speakers.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('raw_transcript', type=Path)
    p.add_argument('speaker_turns', type=Path)
    p.add_argument('output', type=Path, help='Meeting directory for transcript.json/md')
    a = p.parse_args()
    targets = [a.output / 'transcript.json', a.output / 'transcript.md']
    if any(path.exists() for path in targets):
        p.error('Labeled transcript already exists; choose a new output directory.')
    raw = json.loads(a.raw_transcript.read_text(encoding='utf-8'))
    diarization = json.loads(a.speaker_turns.read_text(encoding='utf-8'))
    if Path(raw['source']).resolve() != Path(diarization['source']).resolve():
        p.error('Transcript and speaker turns come from different audio files.')
    result = label(raw, diarization)
    a.output.mkdir(parents=True, exist_ok=True)
    targets[0].write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    targets[1].write_text('# Transcript\n\n' + '\n\n'.join(
        f'[{stamp(s["start"])}–{stamp(s["end"])}] {s["speaker"] or "Speaker uncertain"}: {s["text"]}'
        for s in result['segments']), encoding='utf-8')
    print(targets[0])


if __name__ == '__main__':
    main()
