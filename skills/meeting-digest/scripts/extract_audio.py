"""Extract mono audio, retaining its offset relative to the video timeline."""
import argparse
import json
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('Output already exists; choose a new path.')
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_format', '-show_streams',
                            '-of', 'json', str(a.video)], check=True, capture_output=True, text=True)
    data = json.loads(probe.stdout)
    streams = [s for s in data['streams'] if s['codec_type'] == 'audio']
    if not streams:
        p.error('Recording has no audio stream.')
    origin = float(data.get('format', {}).get('start_time', 0))
    offset = float(streams[0].get('start_time', origin)) - origin
    filters = ['asetpts=PTS-STARTPTS']
    if offset > 0:
        filters.append(f'adelay={round(offset * 1000)}:all=1')
    elif offset < 0:
        filters.extend([f'atrim=start={-offset}', 'asetpts=PTS-STARTPTS'])
    a.output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(a.video),
                    '-map', '0:a:0', '-vn', '-af', ','.join(filters), '-ac', '1',
                    '-ar', '16000', '-c:a', 'pcm_s16le', str(a.output)], check=True)
    print(a.output)


if __name__ == '__main__':
    main()
