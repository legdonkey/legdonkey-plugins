import music from './music.json' with {type:'json'};
import assets from './voice-assets.json' with {type:'json'};
export const FPS=30, AUDIO_OFFSET=1.29;
export const beatF=(beat:number)=>Math.round(((music.anchors.find(a=>a.beat===beat)?.seconds ?? music.t0+beat*music.T)+AUDIO_OFFSET/FPS)*FPS);
export const TOTAL=beatF(130);
const boundaries=[0,4,22,46,58,82,102,118,130];
export const SHOTS=[
 {id:'hook',label:'先听，再说'}, {id:'voices',label:'同一句话，三种声音'},
 {id:'models',label:'选对模型'}, {id:'ranking',label:'榜单前二，也在这里'},
 {id:'clone',label:'把自己的声音留下来'}, {id:'say',label:'选中，就能听'},
 {id:'export',label:'把声音带进创作'}, {id:'outro',label:'bailian-tts'},
].map((s,i)=>({...s,from:i===0?0:beatF(boundaries[i]),duration:beatF(boundaries[i+1])-(i===0?0:beatF(boundaries[i]))}));
export const DEMOS=[
 {key:'demos-0',name:'许南川',trait:'沉稳 · 叙事',from:beatF(4)+4},
 {key:'demos-1',name:'于小云',trait:'明亮 · 活力',from:beatF(10)+4},
 {key:'demos-2',name:'许玉远',trait:'知性 · 质感',from:beatF(16)+4},
];
const cue=(key:keyof typeof assets,from:number,kind:string)=>({key,from,duration:assets[key].frames,src:assets[key].src,text:assets[key].text,volume:1,kind});
export const VOICES=[...DEMOS.map(d=>cue(d.key as keyof typeof assets,d.from,'demo')),
 cue('remake-0',SHOTS[2].from+30,'narration'),cue('ranking-0',SHOTS[3].from+12,'narration'),cue('remake-1',SHOTS[4].from+12,'narration'),
 cue('remake-2',SHOTS[5].from+6,'narration'),cue('read-demo-0',SHOTS[5].from+144,'read'),
 cue('remake-4',SHOTS[6].from+12,'narration'),cue('remake-5',SHOTS[7].from+12,'narration')];
// 字幕仅导出独立 SRT，成片和工作台均不叠底部旁白字幕。
export const CAPTIONS=VOICES.flatMap((v,i)=>{const chunks=v.text.replace(/\[[^\]]+\]/g,'').match(/[^，。！？]+[，。！？]?/g)||[];const count=chunks.join('').length;let n=0;return chunks.map((text,j)=>{const start=Math.round(n/count*v.duration);n+=text.length;return{id:`caption-${i}-${j}`,from:v.from+start,duration:Math.round(n/count*v.duration)-start,text};});});
// 音源峰值为本次原创/派生音效实测值，build-sound.py 生成后核对。
const PEAK={sweep:.285,land:.005,key:.005,'wood-swish':.065};
const sfx=(shot:number,offset:number,name:keyof typeof PEAK,volume:number,duration:number)=>({from:Math.max(0,Math.round(SHOTS[shot].from+offset-PEAK[name]*FPS-AUDIO_OFFSET)),duration,src:`audio/original/${name}.wav`,volume,target:SHOTS[shot].from+offset});
export const SFX=[
 sfx(0,15,'land',.8,15),sfx(1,0,'sweep',.75,16),
 sfx(1,beatF(10)-SHOTS[1].from,'wood-swish',.75,17),sfx(1,beatF(16)-SHOTS[1].from,'sweep',.65,16),
 sfx(2,58,'sweep',.85,16),sfx(3,8,'land',.85,15),
 sfx(4,62,'key',.8,5),sfx(4,150,'wood-swish',.8,17),sfx(4,276,'land',.7,15),
 sfx(5,120,'key',1,5),sfx(6,64,'sweep',.9,16),sfx(6,140,'land',.7,15),
 sfx(7,54,'land',.9,15),
];
export const BGM={from:0,duration:TOTAL,src:'audio/bgm/bed.wav',volume:1};
