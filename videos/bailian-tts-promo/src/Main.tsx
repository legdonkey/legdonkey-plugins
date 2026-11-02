import React from 'react';
import {AbsoluteFill,Audio,Img,Sequence,staticFile,useCurrentFrame,interpolate,Easing} from 'remotion';
import {PageCam} from './lib/PageCam';
import {BGM,DEMOS,SHOTS,SFX,VOICES,TOTAL,beatF} from './timeline';
import audio from './voice-assets.json';
import layout from '../public/textures/remake/layout.json';

export const C={room:'#111113',panel:'#1a1b1e',inset:'#222327',line:'#2c2e33',ink:'#ece8e1',muted:'#a8a196',gold:'#c9b27c',ok:'#8fcfa6'};
const FONT='"PingFang SC", -apple-system, sans-serif';
const EASE=Easing.bezier(.22,1,.36,1);
const ramp=(f:number,start:number,duration:number,easing=EASE)=>interpolate(f,[start,start+duration],[0,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp',easing});
const mix=(a:number,b:number,p:number)=>a+(b-a)*p;
type Props={title?:string;duration?:number};
export const Stage:React.FC<React.PropsWithChildren>=({children})=><AbsoluteFill style={{background:C.room,color:C.ink,fontFamily:FONT,overflow:'hidden'}}>{children}</AbsoluteFill>;
const Mark=()=> <div style={{position:'absolute',right:90,top:50,fontSize:30,letterSpacing:2,color:C.muted}}>bailian-tts</div>;
const Kicker:React.FC<{children:React.ReactNode}>=({children})=><div style={{position:'absolute',left:96,top:58,fontSize:32,color:C.muted,letterSpacing:3}}>{children}</div>;
const Footer:React.FC<{children:React.ReactNode}>=({children})=><div style={{position:'absolute',left:96,right:96,bottom:42,fontSize:32,color:C.muted}}>{children}</div>;

// voice-waveform-live 的64条、1.6f历史位移、sin^.8空间权重；用实际人声包络替代伪信号。
const VoiceWave:React.FC<{voice:keyof typeof audio;frame:number;width?:number;height?:number;color?:string}>=({voice,frame,width=750,height=150,color=C.ink})=>{
 const data=audio[voice].envelope;
 const active=frame>=0&&frame<data.length;
 const collapse=active?1:1-ramp(frame,data.length,12);
 return <div style={{width,height,display:'flex',gap:5,alignItems:'center'}}>{Array.from({length:64},(_,i)=>{
  const sample=Math.floor(frame-(63-i)*1.6), value=sample>=0&&sample<data.length?data[sample]:0;
  const weight=Math.pow(Math.sin(i/63*Math.PI),.8);
  const h=Math.max(5,value*weight*height*collapse);
  return <span key={i} style={{flex:1,height:h,borderRadius:8,background:h>7?color:C.muted,opacity:.35+.65*i/63}}/>;
 })}</div>;
};

// 元素切片按原始宽高比进入 PageCam；1920 是组件的页面坐标基准，不改图片比例。
const UI:React.FC<{name:string;frame:number;x?:number;y?:number;width?:number;tilt?:number}>=({name,frame,x=1280,y=550,width=660,tilt=-8})=>{
 const box=(layout as Record<string,{width:number;height:number}>)[name];
 const h=box.height/box.width*1920, z=width/1920;
 const key=(frame:number,shift:number,zoom:number,rotY:number)=>({frame,cx:960-(x+shift-960)/zoom,cy:h/2-(y-540)/zoom,zoom,rotY,persp:2400});
 return <PageCam src={`textures/remake/${name}.png`} pageH={h} frame={frame} keys={[key(0,160,z*.96,tilt),key(24,0,z,0),key(180,0,z,0)]}/>;
};

export const Hook:React.FC<Props>=({title='先听，再说。'})=>{
 const f=useCurrentFrame(),p=ramp(f,2,18),out=ramp(f,48,14,Easing.bezier(.7,0,.9,.5));
 return <Stage><Mark/><div style={{position:'absolute',left:0,right:0,top:300,textAlign:'center',fontSize:210,fontWeight:300,letterSpacing:8,opacity:p*(1-out),transform:`translateY(${(1-p)*65-out*80}px) scale(${mix(1.12,1,p)})`,filter:`blur(${(1-p)*16}px)`}}>{title}</div><div style={{position:'absolute',left:540,top:660,width:840,height:2,background:C.line}}/><div style={{position:'absolute',left:540,top:660,width:840*ramp(f,16,27),height:2,background:C.gold}}/><div style={{position:'absolute',left:0,right:0,top:735,textAlign:'center',fontSize:40,color:C.muted,opacity:ramp(f,20,16)*(1-out)}}>同一句文案，听见不同可能。</div></Stage>;
};

export const Voices:React.FC<Props>=()=>{
 const f=useCurrentFrame(),global=f+SHOTS[1].from;
 const i=global<DEMOS[1].from-4?0:global<DEMOS[2].from-4?1:2;
 const d=DEMOS[i],local=global-(d.from-4),p=ramp(local,0,16),tail=ramp(f,SHOTS[1].duration-16,16);
 return <Stage><UI name={`voice-${i}`} frame={local} x={1360} y={560} width={690}/><Mark/><Kicker>真实合成试听 / {i+1} · 3</Kicker>
 <div style={{position:'absolute',left:110,top:220,fontSize:42,color:C.muted}}>同一句话，三种声音。</div>
 <div style={{position:'absolute',left:104,top:335,fontSize:142,fontWeight:300,opacity:p,transform:`translateX(${(1-p)*-120}px)`}}>{d.name}</div>
 <div style={{position:'absolute',left:115,top:525,fontSize:42,color:C.muted,opacity:p}}>{d.trait}</div>
 <div style={{position:'absolute',left:110,top:655}}><VoiceWave voice={d.key as keyof typeof audio} frame={global-d.from} width={750}/></div>
 <div style={{position:'absolute',right:80,top:180,textAlign:'center'}}><div style={{fontSize:110,fontWeight:200,lineHeight:1}}>68</div><div style={{fontSize:28,color:C.muted,marginTop:16}}>系统音色</div></div>
 <Footer>Flash 内置音色清单 · 声音不是示意，三段均由项目实际生成</Footer>
 <div style={{position:'absolute',bottom:0,left:0,height:4,width:`${(i+p)/3*100}%`,background:C.gold,opacity:1-tail}}/>
 </Stage>;
};

const MODEL_INFO=[
 {name:'Flash',tag:'让声音有性格',lines:['音色 / 情绪 / 方言','自己的声音，也能复刻']},
 {name:'Next',tag:'描述你想要的声音',lines:['用文字设定声音特征','不绑定 Flash 音色 ID']},
 {name:'Eleven v4',tag:'固定音色，细腻表达',lines:['账号音色与独立收藏','支持文本内情感标签']},
 {name:'v4 Turbo',tag:'低延迟模型选项',lines:['复用 v4 音色与收藏','WebSocket 接收音频']},
];
export const Models:React.FC<Props>=({title='选对模型'})=>{
 const f=useCurrentFrame(),dem=ramp(f,36,26,Easing.bezier(.6,0,.18,1)),show=ramp(f,0,16);
 const scale=mix(1,.22,dem),x=mix(960,216,dem),y=mix(540,196,dem);
 const focusBeats=[29,33,37,41].map(n=>beatF(n)-SHOTS[2].from),active=focusBeats.reduce((a,t,i)=>f>=t?i:a,0),travel=ramp(f,focusBeats[active],24,Easing.bezier(.6,0,.18,1));
 const pose=(i:number,a:number)=>a<0?{x:96+i*438,y:310,w:410,h:510,hero:0,compact:0}:i===a?{x:96,y:310,w:890,h:510,hero:1,compact:0}:{x:1040,y:310+(i<a?i:i-1)*170,w:780,h:145,hero:0,compact:1};
 return <Stage><Mark/><div style={{position:'absolute',left:x,top:y,fontSize:220,fontWeight:400,whiteSpace:'nowrap',opacity:show,transform:`translate(${-50*(1-dem)}%,-50%) scale(${scale})`,transformOrigin:'left center'}}>{title}</div>
 <div style={{position:'absolute',left:96,top:175,fontSize:32,color:C.gold,opacity:ramp(f,56,12)}}>04 /</div>
 {MODEL_INFO.map((m,i)=>{const p=ramp(f,48+[0,6,14,24][i],22),a=pose(i,active-1),b=pose(i,active),hero=mix(a.hero,b.hero,travel),compact=mix(a.compact,b.compact,travel),lit=i===active;return <div key={m.name} style={{position:'absolute',left:mix(a.x,b.x,travel),top:mix(a.y,b.y,travel),width:mix(a.w,b.w,travel),height:mix(a.h,b.h,travel),boxSizing:'border-box',border:`1px solid ${lit?C.gold:C.line}`,borderRadius:12,background:lit?C.inset:C.panel,opacity:p,transform:`translateY(${(1-p)*40}px)`,clipPath:`inset(0 ${(1-p)*70}% 0 0)`,zIndex:lit?5:i===active-1?4:1,overflow:'hidden'}}><div style={{position:'absolute',left:30,top:26,fontSize:30,color:lit?C.gold:C.muted}}>0{i+1}</div><div style={{position:'absolute',left:mix(30,100,compact),top:mix(92,20,compact),fontSize:52+hero*26-compact*10,fontWeight:300,whiteSpace:'nowrap'}}>{m.name}</div><div style={{position:'absolute',left:mix(30,100,compact),top:mix(205+hero*20,85,compact),fontSize:34+hero*18-compact*6,color:C.ink,lineHeight:1.5,whiteSpace:'nowrap'}}>{m.tag}</div><div style={{position:'absolute',left:30,right:30,top:335+hero*20,opacity:1-compact}}><div style={{height:1,background:C.line,marginBottom:24}}/>{m.lines.map(l=><div key={l} style={{fontSize:29+hero*7,color:C.muted,lineHeight:1.8,whiteSpace:'nowrap'}}>{l}</div>)}</div></div>})}
 <div style={{position:'absolute',left:96,top:870,fontSize:40,opacity:ramp(f,90,25)}}>同一个工作台，按需求切换。</div>
 <Footer>Turbo 仍在完整合成后播放；不同模型的音色和指令能力不混用。</Footer></Stage>;
};

export const Ranking:React.FC<Props>=({title='排名前二，也在你的工作台。'})=>{
 const f=useCurrentFrame(),p=ramp(f,0,18);
 return <Stage><Mark/><Kicker>不是自评，是盲听投票。</Kicker><div style={{position:'absolute',left:96,top:155,fontSize:82,fontWeight:300,opacity:p,transform:`translateY(${(1-p)*30}px)`}}>{title}</div><div style={{position:'absolute',left:140,top:330,width:1640,overflow:'hidden',borderRadius:10,transform:`scale(${mix(1.035,1,ramp(f,4,36))})`}}><Img src={staticFile('textures/remake/aa-focus.png')} style={{width:1640,display:'block'}}/></div><div style={{position:'absolute',left:140,top:930,fontSize:32,color:C.muted}}>Artificial Analysis · Provider Voice Arena · 核查日期 2026.11.02</div><div style={{position:'absolute',left:140,top:985,fontSize:29,color:C.muted}}>当日排序前二，排名区间均为 1–2；不是中文专项榜或声音克隆榜。排名会变化。</div></Stage>;
};

export const Clone:React.FC<Props>=()=>{
 const f=useCurrentFrame();const stage=f<62?0:f<150?1:f<276?2:3;
 const names=['clone-ready','clone-record','clone-grade','clone-done'];
 const start=[0,62,150,276][stage],width=[1450,1080,900,1500][stage];
 const waiting=f>=246&&f<276;
 return <Stage><AbsoluteFill style={{opacity:stage===2?.20:1}}><UI name={names[stage]} frame={f-start} x={stage===2?1190:1000} y={stage===2?570:600} width={width} tilt={stage===0?-8:0}/></AbsoluteFill><Mark/><Kicker>声音复刻 / 一个工作台，走完。</Kicker>
 <div style={{position:'absolute',left:100,top:140,fontSize:88,fontWeight:300}}>{['录一段。','留住你的声音。','先检查，再提交。','下次配音，直接用。'][stage]}</div>
 {stage===2&&<div style={{position:'absolute',left:110,top:380,fontSize:60,fontWeight:300,lineHeight:1.7}}>时长<br/>音量<br/>破音<div style={{fontSize:32,color:C.muted,marginTop:35}}>音量偏低或削波时，<br/>提示重新录音。</div></div>}
 {stage===2&&<div style={{position:'absolute',inset:0,opacity:ramp(f,150,18)}}><Img src={staticFile('textures/remake/proof-pass.png')} style={{position:'absolute',left:820,top:350,width:520}}/><div style={{position:'absolute',left:830,top:550,fontSize:40}}>录完先质检，合适再提交。</div><Img src={staticFile('textures/remake/proof-submit.png')} style={{position:'absolute',left:820,top:680,width:360,transform:`scale(${1-.05*ramp(f,240,4)})`}}/></div>}
 {stage===3&&<Img src={staticFile('textures/remake/proof-saved.png')} style={{position:'absolute',left:1400,top:330,width:320,opacity:ramp(f,276,18)}}/>}
 {waiting&&<AbsoluteFill style={{background:'rgba(17,17,19,.9)',justifyContent:'center',alignItems:'center'}}><div style={{fontSize:78,fontWeight:300}}>等待音色就绪<span style={{opacity:.35+.65*(Math.sin(f*.2)+1)/2}}>…</span></div><div style={{fontSize:34,color:C.muted,marginTop:35}}>此处压缩等待，不代表实际合成耗时</div></AbsoluteFill>}
 <Footer>推荐录音 10–20 秒 · Flash 专属 · 自有或已获授权的声音 · 流程状态演示</Footer></Stage>;
};

export const Say:React.FC<Props>=()=>{
 const f=useCurrentFrame(),sel=ramp(f,40,40,Easing.bezier(.4,0,.6,1)),key=ramp(f,98,18),pressed=ramp(f,118,4)*(1-ramp(f,126,10));
 const now=f<144?'准备声音…':'正在朗读 · 于小云';
 return <Stage><Mark/><Kicker>把眼睛的工作，交给耳朵。</Kicker>
 <div style={{position:'absolute',left:120,top:175,width:1680,height:700,border:`1px solid ${C.line}`,borderRadius:12,background:C.panel,overflow:'hidden',transform:`scale(${mix(1.06,1,ramp(f,0,40))})`}}>
 <div style={{borderBottom:`1px solid ${C.line}`,padding:'22px 42px',fontSize:30,color:C.muted}}>创作笔记 / 一段你每天都会遇到的文字</div>
 <div style={{padding:'35px 60px',fontSize:40,lineHeight:1.9,color:C.muted}}><div style={{opacity:f>85?.3:.7}}>做一条产品短片，不应该把时间都耗在重复的准备工作上。</div><div style={{opacity:f>85?.3:.7}}>找音色、写调用、导出音频，再把字幕逐句放进时间线。</div><div style={{position:'relative',display:'inline-block',fontSize:58,color:C.ink,margin:'32px 0 26px',padding:'7px 12px'}}><div style={{position:'absolute',left:0,top:0,bottom:0,width:`${sel*100}%`,background:'#3a3324'}}/><span style={{position:'relative'}}>把文案交给 AI，把时间留给创作。</span></div><div style={{opacity:.3}}>听见结果，再回到真正值得打磨的想法。</div></div>
 </div>
 <div style={{position:'absolute',left:1420,top:750,width:330,padding:'24px 0',textAlign:'center',fontSize:54,border:`1px solid ${f>=118?C.gold:C.line}`,borderRadius:10,background:C.room,color:f>=118?C.gold:C.ink,opacity:key,transform:`translateY(${(1-key)*80}px) scale(${1-.06*pressed})`}}>⌃ ⌥ ⌘ S</div>
 {f>=124&&<div style={{position:'absolute',left:190,top:730}}><div style={{fontSize:30,color:C.muted,marginBottom:4}}>{now}</div>{f>=144&&<VoiceWave voice="read-demo-0" frame={f-144} width={1000} height={72}/>}</div>}
 <Footer>macOS · 需先配置按键与权限 · 完整合成后播放 · 操作演示</Footer></Stage>;
};

export const Export:React.FC<Props>=()=>{
 const f=useCurrentFrame(),split=ramp(f,35,45,Easing.bezier(.4,0,.2,1));
 return <Stage><Mark/><Kicker>声音，不停在试听里。</Kicker><div style={{position:'absolute',left:100,top:155,fontSize:88,fontWeight:300}}>刚才的声音，现在就能用。</div>
 <div style={{position:'absolute',left:mix(550,120,split),top:330,width:620,height:430,padding:40,boxSizing:'border-box',border:`1px solid ${C.line}`,background:C.panel,borderRadius:12,transform:`scale(${mix(1.1,1,split)})`}}><div style={{fontSize:30,color:C.muted}}>三种声音的品牌短片.txt</div><div style={{fontSize:54,fontWeight:300,lineHeight:1.6,marginTop:50}}>让想法，<br/>被听见。</div><div style={{fontSize:32,color:C.muted,marginTop:35}}>许南川 / 于小云 / 许玉远</div></div>
 {DEMOS.map((d,i)=>{const p=ramp(f,54+[0,16,26][i],32),asset=audio[d.key as keyof typeof audio];return <div key={d.key} style={{position:'absolute',left:870,top:330+i*140,width:900,height:116,borderBottom:`1px solid ${C.line}`,opacity:p,transform:`translateX(${(1-p)*-180}px)`,display:'flex',alignItems:'center',gap:25}}><span style={{fontSize:32,width:145}}>00{i+1}.wav</span><div style={{display:'flex',gap:5,width:510,alignItems:'center',height:70}}>{Array.from({length:64},(_,k)=><span key={k} style={{width:5,height:4+asset.envelope[Math.min(asset.envelope.length-1,Math.floor(k/64*asset.envelope.length))]*64,background:C.ink}}/>)}</div><span style={{fontSize:32,color:C.muted}}>{asset.duration.toFixed(2)}s</span></div>})}
 <div style={{position:'absolute',left:870,top:790,display:'flex',gap:28,opacity:ramp(f,125,25),transform:`translateY(${(1-ramp(f,125,25))*40}px)`}}>{['all.wav','subtitles.srt'].map(x=><div key={x} style={{fontSize:40,padding:'20px 30px',border:`1px solid ${C.gold}`,borderRadius:8}}>{x}</div>)}</div>
 <Footer>本片三段试听的实际生成产物 · 分段音频 / 拼接音轨 / 配套字幕</Footer></Stage>;
};

export const Outro:React.FC<Props>=({title='bailian-tts'})=>{
 const f=useCurrentFrame(),p=ramp(f,8,46),slide=ramp(f,20,45);
 return <Stage><div style={{position:'absolute',left:0,right:0,top:250,textAlign:'center',fontSize:160,fontWeight:200,letterSpacing:3,opacity:p,transform:`scale(${mix(1.12,1,p)})`}}>{title}</div><div style={{position:'absolute',left:0,right:0,top:470,textAlign:'center',fontSize:68,fontWeight:300,opacity:ramp(f,35,30)}}>表达，不止一种声音。</div><div style={{position:'absolute',left:0,right:0,top:640,display:'flex',justifyContent:'center',gap:60,fontSize:40,color:C.muted}}>{['Claude Code','Codex','Pi'].map((x,i)=><div key={x} style={{opacity:slide,transform:`translateX(${(1-slide)*(i-1)*220}px)`}}>{x}</div>)}</div><div style={{position:'absolute',left:0,right:0,top:800,textAlign:'center',fontSize:38,opacity:ramp(f,56,25)}}>github.com/legdonkey/legdonkey-plugins</div><div style={{position:'absolute',left:0,right:0,top:875,textAlign:'center',fontSize:32,color:C.muted,opacity:ramp(f,66,24)}}>安装 bailian-tts · 告诉 AI，你想怎么说。</div></Stage>;
};
export const SCENES=[Hook,Voices,Models,Ranking,Clone,Say,Export,Outro];
export const Main:React.FC<{bgm?:boolean}>=({bgm=true})=><AbsoluteFill style={{background:C.room}}>{SHOTS.map((s,i)=>{const Scene=SCENES[i];return <Sequence key={s.id} from={s.from} durationInFrames={s.duration}><Scene duration={s.duration}/></Sequence>})}{[...VOICES,...SFX].map((a,i)=><Sequence key={i} from={a.from} durationInFrames={a.duration}><Audio src={staticFile(a.src)} volume={a.volume}/></Sequence>)}{bgm&&<Audio src={staticFile(BGM.src)} volume={BGM.volume}/>}</AbsoluteFill>;
