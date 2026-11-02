"""成片技术检查：实际混音偏移、切点、音效、双版本画面和音频响度。"""
import datetime,hashlib,json,subprocess,re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
VIDEO=ROOT/'out/bailian-tts-promo-remake.mp4'
NO_BGM=ROOT/'out/bailian-tts-promo-remake-nobgm.mp4'
plan=json.loads(subprocess.check_output(['node','--input-type=module','-e',"import {SHOTS,SFX,VOICES,FPS,TOTAL} from './src/timeline.ts'; console.log(JSON.stringify({shots:SHOTS,sfx:SFX,voices:VOICES,fps:FPS,total:TOTAL}));"],cwd=ROOT))
def pcm(path):
    return np.frombuffer(subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-f','f32le','-ac','1','-ar','12000','-']),dtype='<f4')
def offset(y,source,expected):
    start=max(0,round((expected-.12)*12000));window=y[start:start+len(source)+3600]
    corr=np.correlate(window,source,'valid');peak=int(np.argmax(corr))
    match=window[peak:peak+len(source)]
    confidence=float(np.dot(match,source)/(np.linalg.norm(match)*np.linalg.norm(source)+1e-12))
    return (start+peak)/12000-expected,confidence

y=pcm(VIDEO);without_music=pcm(NO_BGM);bed=pcm(ROOT/'public/audio/bgm/bed.wav')
report={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'video':str(VIDEO),'sha256':hashlib.sha256(VIDEO.read_bytes()).hexdigest(),'bgm_probes':[],'sfx_probes':[],'limits':'技术检测不代替主观听音或连续播放审美验收。'}
music=json.loads((ROOT/'analysis/beat_data.json').read_text())
for shot_index,shot in enumerate(plan['shots'][1:],1):
    expected=shot['from']/30
    index=int(expected*12000);x=bed[index:index+24000]
    delay,confidence=offset(y,x,expected)
    cut_error=(music['anchors'][shot_index]['seconds']+delay)*30-shot['from']
    assert abs(cut_error)<3,(shot,cut_error)
    report['bgm_probes'].append({'shot':shot['id'],'output_delay_frames':delay*30,'cut_error_frames':cut_error,'correlation':confidence})
manifest=json.loads((ROOT/'public/audio/sound-manifest.json').read_text())
metadata={x['file']:x for x in manifest['assets']}
for cue in plan['sfx']:
    x=pcm(ROOT/'public'/cue['src'])[:3600]
    delay,confidence=offset(y,x,cue['from']/30)
    error=cue['from']+delay*30+metadata[cue['src']]['energy_peak_seconds']*30-cue['target']
    no_music_delay,no_music_confidence=offset(without_music,x,cue['from']/30)
    assert abs(no_music_delay-delay)*30<.5
    report['sfx_probes'].append({'target':cue['target'],'peak_error_frames':round(error,3),'correlation':confidence,'nobgm_correlation':no_music_confidence,'dual_audio_start_difference_frames':round((no_music_delay-delay)*30,4)})
    assert abs(error)<.55,(cue,error)
# 相同源时间线的两次渲染，逐帧比较解码视频，不把音轨哈希当画面哈希。
video_hashes=[]
for file in [VIDEO,NO_BGM]:
    lines=subprocess.check_output(['ffmpeg','-v','error','-i',str(file),'-map','0:v:0','-f','framemd5','-']).decode().splitlines()
    video_hashes.append([line.split(',')[-1].strip() for line in lines if line and not line.startswith('#')])
assert len(video_hashes[0])==plan['total']
report['video_frame_count']=len(video_hashes[0]);report['dual_version_identical_frames']=video_hashes[0]==video_hashes[1]
# 两次有损编码可能有末位像素差；报告真实结果，另外比较全部对应帧的SSIM。
ssim_file=ROOT/'out/dual-version-ssim.log'
subprocess.run(['ffmpeg','-v','error','-y','-i',str(VIDEO),'-i',str(NO_BGM),'-lavfi',f'[0:v][1:v]ssim=stats_file={ssim_file}','-f','null','-'],check=True)
ssim=[float(x) for x in re.findall(r'All:([0-9.]+)',ssim_file.read_text())]
assert len(ssim)==plan['total']
report['dual_version_ssim_min']=min(ssim);report['dual_version_ssim_mean']=float(np.mean(ssim))
assert min(ssim)>.995, '双版本画面不等价'
report['dual_version_note']='同一时间线；有损编码非逐像素相同，全部对应帧SSIM检查通过。'
(ROOT/'out/verification-remake.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
