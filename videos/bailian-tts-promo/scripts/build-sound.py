"""按用户授权生成原创短音效，并按唯一时间线制作闪避BGM；不联网。"""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import wave
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/audio/original'
OUT.mkdir(exist_ok=True)
SR = 48000
rng = np.random.default_rng(20261102)
assets = []

def write_wav(path, samples):
    samples = np.asarray(samples)
    assert np.isfinite(samples).all() and abs(samples).max() < 1
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1 if samples.ndim == 1 else samples.shape[1])
        out.setsampwidth(2); out.setframerate(SR)
        out.writeframes((samples * 32767).astype('<i2').tobytes())

def filtered_noise(seconds, low, high):
    n = round(seconds * SR)
    spectrum = np.fft.rfft(rng.normal(size=n))
    freq = np.fft.rfftfreq(n, 1 / SR)
    spectrum *= ((freq >= low) & (freq <= high))
    result = np.fft.irfft(spectrum, n=n)
    return result / max(np.std(result), 1e-9)

def save(name, samples, peak_db, description):
    samples = samples / abs(samples).max() * 10 ** (peak_db / 20)
    path = OUT / f'{name}.wav'
    write_wav(path, samples)
    energy = np.array([np.mean(samples[i:i+480] ** 2) for i in range(0, len(samples), 480)])
    asset = {'file': f'audio/original/{name}.wav', 'duration_seconds': len(samples) / SR,
             'energy_peak_seconds': (int(np.argmax(energy)) + .5) * .01,
             'sample_peak_dbfs': peak_db, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
             'source': '本工程原创程序合成；用户已同意', 'description': description}
    assets.append(asset)
    print(json.dumps(asset, ensure_ascii=False))

t = np.arange(round(.52 * SR)) / SR
sweep = filtered_noise(.52, 500, 7000) * np.sin(np.pi * t / .52) ** 2.5
save('sweep', sweep, -9, '带限气流短扫声，配合轨道展开与页面转场，无提示音音阶')
t = np.arange(round(.5 * SR)) / SR
body = np.sin(2*np.pi*(90*t - 40*t*t)) * np.exp(-t*16)
attack = filtered_noise(.5, 100, 2600) * np.exp(-t*70) * .18
save('land', (body + attack) * np.minimum(t/.004, 1), -10, '低频短落点，无长混响，配合文件落定与品牌收束')
t = np.arange(round(.16 * SR)) / SR
noise = filtered_noise(.16, 350, 6500)
click = noise * (np.exp(-np.maximum(t-.008, 0)*180)*(t>=.008) + .45*np.exp(-np.maximum(t-.075, 0)*160)*(t>=.075))
click += .25*np.sin(2*np.pi*210*t)*np.exp(-t*90)
save('key', click, -8, '模拟按键压下与回弹的双瞬态短声；原创合成，非真实键盘录音')

# 沿用已获许可的真实转场声，但先归一到可用电平，不把低电平素材原样埋进混音。
raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(ROOT/'public/audio/sfx/fs-485279.mp3'), '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'])
save('wood-swish', np.frombuffer(raw, dtype='<f4'), -9, '派生自 Freesound fs:485279 / Joao_Janz / CC0-1.0；单声道、峰值归一化，不是原创声源')
assets[-1]['source'] = 'https://freesound.org/people/Joao_Janz/sounds/485279/'
assets[-1]['license'] = 'CC0-1.0'

# 章节按真实音乐瞬态编排；试听比旁白多闪避，听清不同音色。
plan = json.loads(subprocess.check_output(['node', '--input-type=module', '-e', "import {VOICES,FPS,TOTAL} from './src/timeline.ts'; console.log(JSON.stringify({seconds:TOTAL/FPS,voices:VOICES.map(v=>({start:v.from/FPS,duration:v.duration/FPS,kind:v.kind}))}));"], cwd=ROOT))
seconds = plan['seconds']
bgm_source = ROOT / 'public/audio/bgm/house-vibez.mp3'
normalized = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(bgm_source), '-t', str(seconds), '-af', 'loudnorm=I=-19:TP=-2:LRA=7', '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-'])
music = np.frombuffer(normalized, dtype='<f4').reshape(-1, 2).copy()
time = np.arange(len(music)) / SR
envelope = np.full(len(music), .62)
for cue in plan['voices']:
    start, duration = cue['start'], cue['duration']
    attack = np.clip((time-(start-.20))/.20,0,1)
    release = np.clip((start+duration+.40-time)/.40,0,1)

    floor = .18 if cue['kind'] in ['demo','read'] else .34
    envelope = np.minimum(envelope,.62-(.62-floor)*np.minimum(attack,release))
envelope *= np.minimum(np.clip(time/.35,0,1),np.clip((seconds-time)/1.5,0,1))
write_wav(ROOT/'public/audio/bgm/bed.wav', music*envelope[:,None])
report = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'seed': 20261102, 'assets': assets,
          'bgm': {'title': 'House Vibez', 'artist': 'Lily J',
                  'source': 'https://assets.mixkit.co/music/745/745.mp3',
                  'license': 'Mixkit Stock Music Free License', 'license_url': 'https://mixkit.co/license/#musicFree',
                  'source_sha256': hashlib.sha256(bgm_source.read_bytes()).hexdigest(),
                  'file': 'audio/bgm/bed.wav', 'sha256': hashlib.sha256((ROOT/'public/audio/bgm/bed.wav').read_bytes()).hexdigest(),
                  'processing': f'截取前{seconds:.3f}秒，-19 LUFS规范化；真实试听/朗读系数.18、旁白.34、间隙.62；提前200ms闪避、400ms恢复；首.35秒淡入、尾1.5秒淡出。'}}
(ROOT/'public/audio/sound-manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
