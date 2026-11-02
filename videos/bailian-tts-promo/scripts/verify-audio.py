"""对最终成片复算两处转场声偏移，并记录产物哈希与测量时间。需要本机 numpy。"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
VIDEO = ROOT / 'out/bailian-tts-promo.mp4'
SOURCE = ROOT / 'public/audio/sfx/fs-485279.mp3'

def pcm(path):
    data = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'f32le', '-ac', '1', '-ar', '12000', '-'])
    return np.frombuffer(data, dtype=np.float32)

rendered, source = pcm(VIDEO), pcm(SOURCE)[:2400]
rows = []
for target, scheduled in [(190, 187), (700, 697)]:
    start = round((scheduled / 30 - .12) * 12000)
    window = rendered[start:start + len(source) + 3600]
    offset = int(np.argmax(np.correlate(window, source, 'valid')))
    actual = (start + offset) / 12000 * 30
    error = actual + .065 * 30 - target
    assert abs(error) < .5, f'音画误差超限：{error}'
    rows.append({'target_peak_frame': target, 'scheduled_start_frame': scheduled,
                 'actual_start_frame': actual, 'peak_error_frames': error})
report = {'checked_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'video': str(VIDEO), 'video_sha256': hashlib.sha256(VIDEO.read_bytes()).hexdigest(),
          'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
          'pipeline': 'Remotion 4.0.484 / AAC 48kHz / MP4 / 30fps',
          'method': '源与成片解码为12kHz单声道，取源前200ms，对预计时刻附近窗口做交叉相关；音源峰值滞后65ms，输出管线实测滞后1.29帧。此结果不代替试听。',
          'probes': rows}
(ROOT / 'out/audio-verification-final.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
print(json.dumps(rows, indent=2))
