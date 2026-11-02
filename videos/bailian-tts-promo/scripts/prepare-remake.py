"""从真实生成音频与音乐分析生成可复现的素材数据。"""
import json
from pathlib import Path
import subprocess
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
assets={}
for folder in ['demos','remake','ranking','read-demo']:
    manifest=json.loads((ROOT/f'public/audio/{folder}/manifest.json').read_text())
    for i,item in enumerate(manifest['segments']):
        source=ROOT/f'public/audio/{folder}/{item["file"]}'
        output=source.with_name('norm-'+source.name)
        subprocess.run(['ffmpeg','-v','error','-y','-i',str(source),'-af','loudnorm=I=-16:TP=-1.5:LRA=7','-ar','48000','-ac','1',str(output)],check=True)
        with wave.open(str(output)) as w:
            data=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').astype(float)/32768
            rate=w.getframerate()
        envelope=np.array([np.sqrt(np.mean(data[j:j+1600]**2)) for j in range(0,len(data),1600)])
        peak=max(envelope.max(),1e-8)
        assets[f'{folder}-{i}']={'src':f'audio/{folder}/{output.name}','duration':len(data)/rate,'frames':int(np.ceil(len(data)/rate*30)), 'text':item['text'],'voice':item['voice'],'envelope':[round(float(x/peak),4) for x in envelope]}
(ROOT/'src/voice-assets.json').write_text(json.dumps(assets,ensure_ascii=False))
# 音乐分析只导出小型运行时数据，保留完整分析作证据。
music=json.loads((ROOT/'analysis/beat_data.json').read_text())
(ROOT/'src/music.json').write_text(json.dumps({k:music[k] for k in ['bpm','t0','T','anchors']},ensure_ascii=False,indent=2))
assert len(assets)==11
print({k:round(v['duration'],2) for k,v in assets.items()})
