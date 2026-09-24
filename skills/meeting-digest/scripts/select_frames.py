"""Select local screenshot candidates without calling any model."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import tempfile


def dependencies():
    return {**{n: bool(shutil.which(n)) for n in ('ffmpeg', 'ffprobe')},
            **{n: importlib.util.find_spec(n) is not None for n in ('numpy', 'cv2')}}


def changed(a, b, args):
    mask = cv2.absdiff(a, b) > args.pixel_threshold
    overall = float(mask.mean())
    tiles = [float(t.mean()) for row in np.array_split(mask, 8, axis=0)
             for t in np.array_split(row, 8, axis=1)]
    return overall >= args.change_ratio or max(tiles) >= args.tile_ratio


class Selector:
    def __init__(self, args):
        self.args = args
        self.previous = self.selected = None
        self.selected_at = 0.0
        self.last_motion = 0.0
        self.onset = None

    def consider(self, t, frame):
        reason = None
        if self.previous is None:
            reason = 'initial'
        else:
            moving = changed(frame, self.previous, self.args)
            different = changed(frame, self.selected, self.args)
            if moving:
                self.last_motion = t
            if different and self.onset is None:
                self.onset = t
            if not different:
                self.onset = None
            if different and t - self.last_motion >= self.args.stable_seconds:
                reason = 'settled_change'
            elif different and t - self.selected_at >= self.args.motion_interval:
                reason = 'motion_fallback'
            elif t - self.selected_at >= self.args.max_gap:
                reason = 'coverage'
        self.previous = frame.copy()
        if reason:
            result = dict(timestamp=round(t, 6), reason=reason,
                          approximate_change_start=self.onset)
            self.selected, self.selected_at = frame.copy(), t
            self.onset = None
            return result
        return None


def probe(video):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                             '-of', 'json', str(video)], check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    streams = [s for s in data['streams'] if s['codec_type'] == 'video'
               and not s.get('disposition', {}).get('attached_pic')]
    if not streams:
        raise ValueError('No video stream found.')
    stream = streams[0]
    origin = float(data.get('format', {}).get('start_time', 0))
    return stream, float(data['format']['duration']), max(0, float(stream.get('start_time', origin)) - origin)


def scan(video, stream, offset, args):
    width, height = stream['width'], stream['height']
    filters = ['setpts=PTS-STARTPTS']
    if args.crop:
        x, y, width, height = args.crop
        if x < 0 or y < 0 or width < 8 or height < 8 or x + width > stream['width'] or y + height > stream['height']:
            raise ValueError('Crop is outside the video dimensions or too small.')
        filters.append(f'crop={width}:{height}:{x}:{y}')
    out_width = min(640, width)
    out_height = max(8, round(height * out_width / width))
    filters.extend([f'fps={args.sample_fps}:round=up', f'scale={out_width}:{out_height}', 'format=gray'])
    command = ['ffmpeg', '-v', 'error', '-nostdin', '-noautorotate', '-i', str(video),
               '-map', f'0:{stream["index"]}', '-an', '-vf', ','.join(filters),
               '-f', 'rawvideo', '-pix_fmt', 'gray', 'pipe:1']
    selector = Selector(args)
    selections = []
    size, index = out_width * out_height, 0
    last = None
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
        try:
            while True:
                raw = bytearray()
                while len(raw) < size:
                    part = process.stdout.read(size - len(raw))
                    if not part:
                        break
                    raw.extend(part)
                if not raw:
                    break
                if len(raw) != size:
                    raise RuntimeError('Incomplete decoded frame.')
                frame = np.frombuffer(raw, dtype=np.uint8).reshape(out_height, out_width)
                frame = cv2.GaussianBlur(frame, (3, 3), 0)
                t = offset + index / args.sample_fps
                last = (t, frame)
                choice = selector.consider(t, frame)
                if choice:
                    selections.append(choice)
                index += 1
            code = process.wait()
            if code:
                errors.seek(0)
                raise RuntimeError(errors.read().decode(errors='replace'))
        finally:
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
    if last and changed(last[1], selector.selected, args):
        selections.append(dict(timestamp=round(last[0], 6), reason='final_change',
                               approximate_change_start=selector.onset))
    return selections, index


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('video', nargs='?', type=Path)
    p.add_argument('output', nargs='?', type=Path)
    p.add_argument('--check', action='store_true')
    p.add_argument('--sample-fps', type=float, default=2)
    p.add_argument('--stable-seconds', type=float, default=1)
    p.add_argument('--motion-interval', type=float, default=5)
    p.add_argument('--max-gap', type=float, default=30)
    p.add_argument('--pixel-threshold', type=float, default=20)
    p.add_argument('--change-ratio', type=float, default=.015)
    p.add_argument('--tile-ratio', type=float, default=.12)
    p.add_argument('--crop', help='Comparison region in original pixels: x,y,width,height')
    p.add_argument('--timestamps', help='Extract only these comma-separated times in seconds')
    args = p.parse_args()
    available = dependencies()
    if args.check:
        print(json.dumps(available, indent=2))
        return
    if not args.video or not args.output:
        p.error('video and output are required unless --check is used.')
    if not all(available.values()):
        p.error('Missing dependencies: ' + ', '.join(k for k, v in available.items() if not v))
    for key in ('sample_fps', 'stable_seconds', 'motion_interval', 'max_gap', 'pixel_threshold', 'change_ratio', 'tile_ratio'):
        if not math.isfinite(getattr(args, key)) or getattr(args, key) <= 0:
            p.error(f'--{key.replace("_", "-")} must be positive and finite.')
    if args.change_ratio > 1 or args.tile_ratio > 1 or args.pixel_threshold > 255:
        p.error('Ratios must be <= 1; pixel threshold must be <= 255.')
    if not args.video.is_file():
        p.error('Video does not exist.')
    if (args.output / 'frames.json').exists() or (args.output / 'frames').exists():
        p.error('Frame outputs already exist; use a fresh output directory.')
    if args.crop:
        try:
            args.crop = tuple(int(n) for n in args.crop.split(','))
            if len(args.crop) != 4:
                raise ValueError()
        except ValueError:
            p.error('--crop must contain four integers.')
    global cv2, np
    import cv2
    import numpy as np
    stream, duration, offset = probe(args.video)
    if args.timestamps:
        try:
            times = sorted(set(float(t) for t in args.timestamps.split(',')))
        except ValueError:
            p.error('Timestamps must be numbers separated by commas.')
        if any(not math.isfinite(t) or t < offset or t >= duration for t in times):
            p.error('Timestamps must be within the video stream timeline.')
        choices = [dict(timestamp=t, reason='requested', approximate_change_start=None) for t in times]
        count = 0
    else:
        choices, count = scan(args.video, stream, offset, args)
    if not choices:
        p.error('No frames decoded.')
    frames = args.output / 'frames'
    frames.mkdir(parents=True)
    for i, choice in enumerate(choices, 1):
        name = f'frame-{i:05d}-{choice["timestamp"]:.3f}s.png'
        path = frames / name
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-ss', str(choice['timestamp']),
                        '-noautorotate', '-i', str(args.video), '-map', f'0:{stream["index"]}',
                        '-frames:v', '1', '-update', '1', str(path)], check=True)
        if not path.exists() or path.stat().st_size == 0:
            raise RuntimeError(f'No image produced at {choice["timestamp"]}; no complete manifest written.')
        choice.update(id=f'frame-{i:05d}', path=f'frames/{name}', inspected=False)
    settings = {k: v for k, v in vars(args).items() if k not in ('video', 'output', 'check')}
    result = dict(source=str(args.video.resolve()), duration=duration,
                  timestamp_basis='seconds relative to container start; sampled times approximate',
                  sampled_frames=count, settings=settings, frames=choices)
    target = args.output / 'frames.json'
    target.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'Sampled {count} frames locally; saved {len(choices)} candidates. Manifest: {target}')


if __name__ == '__main__':
    main()
