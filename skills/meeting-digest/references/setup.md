# Dependencies and transcription

The skill drives the locally installed `meeting-digest` command; it does not include a hosted model.

## Local environment

Use a dedicated Python environment where practical. Required: Python 3.10+, FFmpeg/ffprobe on PATH, and the `meeting-digest` package. FFmpeg is a separate executable, not supplied by the Python package named `ffmpeg`. Install it from a trusted platform package or an [FFmpeg-listed Windows build](https://ffmpeg.org/download.html). Then run:

```
python -m pip install git+https://github.com/davin-advasol/meeting_capturer.git
meeting-digest check
```

From a local clone, `python -m pip install -e <clone>` works too. The install pulls its Python dependencies, including PyTorch, so expect a multi-gigabyte download on a clean machine; a GPU setup may require a platform-specific PyTorch build. Local comparison consumes CPU and disk, not model tokens. Keep original recordings outside version control unless the project explicitly tracks them.

## Transcription and speaker labels

For these multi-speaker meetings, use word-timed transcription plus diarization. Prefer the local `faster-whisper` + `pyannote/speaker-diarization-community-1` path below. Reuse another backend only if it can provide compatible word timing and speaker turns. Model weights download on first use and hardware determines speed. Backend setup can proceed alongside local frame selection.

Pyannote Community-1 is released under CC BY 4.0, but access requires accepting its Hugging Face model terms and authenticating locally with a Hugging Face token. Follow the [official setup](https://github.com/pyannote/pyannote-audio) and [model card](https://huggingface.co/pyannote/speaker-diarization-community-1). In your own terminal, run `hf auth login` and paste a read-access token at its private prompt; do not put the token in a command, skill file, output artifact, or chat. Check with `hf auth whoami`. The model weights are downloaded and cached on the first run, not bundled in the skill or requirements file. `meeting-digest diarize` passes the extracted PCM WAV in memory, so TorchCodec decoding and its separate FFmpeg compatibility are not required for this workflow. It runs locally after model download. Run:

```
meeting-digest transcribe <meeting>/audio.wav <meeting> --model small
meeting-digest diarize <meeting>/audio.wav <meeting>/speaker_turns.json
meeting-digest label <meeting>/transcript_raw.json <meeting>/speaker_turns.json <meeting>
```

The `small` model is multilingual. With no `--language`, faster-whisper detects the language; use `--language de` for a German meeting or `--language en` for an English meeting. Avoid English-only model variants such as `small.en` for German. For meetings that switch languages, review the transcript carefully because single-language detection can miss a switch. The first run may download model weights. CPU/int8 is the transcription default; `--device cuda --compute-type float16` is available when the necessary GPU runtime is installed. Diarization uses CUDA when available and labels voices independently of the transcript language. The raw transcript retains word timing; the aligned transcript groups consecutive words by speaker. Review project names, numbers, technical terms, and important speaker assignments against audio/visual evidence. If speaker count is known, `meeting-digest diarize --min-speakers N --max-speakers N` can help.

The audio helper preserves the original timeline by resetting the extracted audio timeline and padding a positive audio/video format-start offset. When using another extractor, verify its offset before trusting transcript-to-frame alignment. Models are imperfect: validate a few spoken transitions against the video, especially for unusual container timestamps.

## Selection tuning

Start at defaults. `--crop` restricts comparison only. Pixel changes below `--pixel-threshold` are ignored; `--change-ratio` measures changed area and `--tile-ratio` catches localized changes on an 8x8 grid. `--stable-seconds` determines when a changed screen settles. `--motion-interval` bounds candidate spacing while moving; `--max-gap` adds coverage candidates even if no change was detected. These are local operations, not semantic importance judgments.

Keep `frames.json` with screenshots: it records exact extraction targets, approximate onset times, reasons, source, and settings. The scan does not save every sampled frame. Full-resolution extraction seeks from the source; original encoding quality remains the limit. Explicit timestamp extraction is useful for cursor gestures, transient menus, or text changes missed by the coarse scan.
