"""音乐节拍、分频瞬态与能量分析；用浮点秒保存，再在时间线中取整到帧。"""
import json
from pathlib import Path
import librosa
import numpy as np
from scipy.signal import butter, sosfilt, find_peaks

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'public/audio/bgm/house-vibez.mp3'
OUT = ROOT/'analysis'; OUT.mkdir(exist_ok=True)
y, sr = librosa.load(SOURCE, sr=22050, mono=True, duration=80)
hop=128
_, beats=librosa.beat.beat_track(y=y,sr=sr,hop_length=hop,tightness=400,units='time')
i=np.arange(len(beats)); (period, origin), *_=np.linalg.lstsq(np.stack([i,np.ones_like(i)],axis=1),beats,rcond=None)
residual=beats-(origin+i*period)
hits=[]
for kind,low,high in [('kick',40,160),('snare',150,3000),('hihat',6000,10000)]:
    band=sosfilt(butter(4,[low,high],btype='band',fs=sr,output='sos'),y)
    env=librosa.onset.onset_strength(y=band,sr=sr,hop_length=hop)
    times=librosa.times_like(env,sr=sr,hop_length=hop)
    peaks,_=find_peaks(env,height=max(env)*.06,distance=int(.09*sr/hop),prominence=max(env)*.025)
    hits.extend({'t':float(times[p]),'s':float(env[p]/max(env)),'k':kind} for p in peaks)
phase=float(origin%period)
truth=np.array(sorted(h['t'] for h in hits));candidates=[]
# 剔除 beat_track 的漏拍/弱攻击离群点，用真实瞬态再次拟合相位与周期。
for _ in range(3):
    index=np.arange(int((65-phase)/period)); grid=phase+index*period
    nearest=np.array([truth[np.argmin(abs(truth-t))] for t in grid])
    keep=abs(nearest-grid)<.025
    (period,phase), *_=np.linalg.lstsq(np.stack([index[keep],np.ones(sum(keep))],axis=1),nearest[keep],rcond=None)
residual=nearest[keep]-(phase+index[keep]*period)
for factor in [.5,1,2]:
    interval=period/factor
    grid=np.arange(phase,min(65,len(y)/sr),interval)
    errors=np.array([truth[np.argmin(abs(truth-t))]-t for t in grid])
    candidates.append({'factor':factor,'bpm':float(60/interval),'match_within_33ms':float(np.mean(abs(errors)<.033)), 'mean_abs_ms':float(np.mean(abs(errors))*1000),'drift_ms':float(np.polyfit(grid,errors,1)[0]*grid[-1]*1000)})
# 稀疏章节切点绑定邻近的真实瞬态，而非伪称每个插值拍都是实测拍。
anchor_beats=[0,4,22,46,58,82,102,118,130]
anchors=[]
for b in anchor_beats:
    expected=phase+b*period
    nearby=[h for h in hits if abs(h['t']-expected)<.06]
    hit=min(nearby,key=lambda h:abs(h['t']-expected)) if nearby else None
    anchors.append({'beat':b,'grid_seconds':float(expected),'seconds':hit['t'] if hit else float(expected),'kind':hit['k'] if hit else 'grid-only','strength':hit['s'] if hit else None})
rms=librosa.feature.rms(y=y,hop_length=sr//2)[0]
result={'source':str(SOURCE),'bpm':float(60/period),'t0':phase,'T':float(period),'fit_max_residual_ms':float(abs(residual).max()*1000),'beats':[float(b) for b in beats],'hits':hits,'rms':[float(v) for v in rms],'anchors':anchors,'sections':[{'from':0,'to':65,'role':'持续节奏底；试听段额外闪避，结尾淡出'}]}
(OUT/'beat_data.json').write_text(json.dumps(result,indent=2,ensure_ascii=False))
(OUT/'grid_drift.json').write_text(json.dumps({'candidates':candidates,'choice':'保持机器鼓点基速；章节切点另外钉真实瞬态。未达到98%时不声称全网格通过。'},indent=2,ensure_ascii=False))
print(json.dumps({k:result[k] for k in ['bpm','t0','T','fit_max_residual_ms','anchors']},ensure_ascii=False,indent=2));print(candidates)
