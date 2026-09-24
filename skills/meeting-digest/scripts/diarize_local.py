"""Find speaker turns in audio with pyannote Community-1."""
import argparse
import json
from pathlib import Path
import wave


def load_pcm16_mono(path):
    """Use the WAV created by extract_audio.py without torchcodec decoding."""
    import numpy as np
    import torch

    with wave.open(str(path), 'rb') as wav:
        if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getcomptype() != 'NONE':
            raise ValueError('Expected uncompressed mono 16-bit PCM WAV from extract_audio.py.')
        sample_rate = wav.getframerate()
        samples = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
    waveform = torch.from_numpy(samples.astype(np.float32) / 32768.0).unsqueeze(0)
    return {'waveform': waveform, 'sample_rate': sample_rate}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('output', type=Path, help='Path to speaker_turns.json')
    p.add_argument('--model', default='pyannote/speaker-diarization-community-1')
    p.add_argument('--min-speakers', type=int)
    p.add_argument('--max-speakers', type=int)
    a = p.parse_args()
    if not a.audio.is_file():
        p.error('Audio file does not exist.')
    if a.output.exists():
        p.error('Output already exists; choose a new path.')
    if a.min_speakers is not None and a.min_speakers < 1:
        p.error('--min-speakers must be positive.')
    if a.max_speakers is not None and a.max_speakers < 1:
        p.error('--max-speakers must be positive.')
    if a.min_speakers and a.max_speakers and a.min_speakers > a.max_speakers:
        p.error('--min-speakers cannot exceed --max-speakers.')
    try:
        import torch
        from pyannote.audio import Pipeline
    except ImportError:
        p.error('Install pyannote.audio and its supported PyTorch dependencies first.')
    try:
        pipeline = Pipeline.from_pretrained(a.model)
    except Exception as exc:
        p.error(f'Could not load pyannote model: {exc}. See references/setup.md for model access.')
    if torch.cuda.is_available():
        pipeline.to(torch.device('cuda'))
    kwargs = {k: v for k, v in [('min_speakers', a.min_speakers),
                               ('max_speakers', a.max_speakers)] if v is not None}
    output = pipeline(load_pcm16_mono(a.audio), **kwargs)
    turns = [dict(start=turn.start, end=turn.end, source_speaker=str(speaker))
             for turn, speaker in output.speaker_diarization]
    turns.sort(key=lambda row: (row['start'], row['end']))
    result = dict(source=str(a.audio.resolve()), backend=a.model,
                  min_speakers=a.min_speakers, max_speakers=a.max_speakers,
                  turns=turns, has_overlaps=any(x['end'] > y['start']
                                                for x, y in zip(turns, turns[1:])))
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(a.output)


if __name__ == '__main__':
    main()
