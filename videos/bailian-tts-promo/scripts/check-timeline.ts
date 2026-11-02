import assert from 'node:assert/strict';
import fs from 'node:fs';
import {SHOTS,VOICES,CAPTIONS,SFX,BGM,TOTAL,FPS} from '../src/timeline.ts';
import assets from '../src/voice-assets.json' with {type:'json'};
assert.equal(SHOTS.length,8);assert.equal(SHOTS[0].from,0);
SHOTS.forEach((s,i)=>assert.equal(s.from+s.duration,i===SHOTS.length-1?TOTAL:SHOTS[i+1].from));
for(const v of VOICES){const shot=SHOTS.find(s=>v.from>=s.from&&v.from<s.from+s.duration)!;assert(shot,`音频不在镜头内：${v.key}`);assert(v.from+v.duration<=shot.from+shot.duration,`音频被截尾：${v.key}`);}
for(const c of CAPTIONS){assert(c.duration>0);assert(c.from+c.duration<=TOTAL);}
for(const a of [...VOICES,...SFX,BGM]){assert(fs.existsSync(new URL(`../public/${a.src}`,import.meta.url)));assert(a.from>=0);assert(a.from+a.duration<=TOTAL);}
assert(TOTAL/FPS>63&&TOTAL/FPS<66);
const reader=VOICES.find(v=>v.kind==='read')!;
assert.equal(assets[reader.key].voice,'yuxiaoyun_v3.1');
assert.equal(reader.text,'把文案交给 AI，把时间留给创作。');
const rank=VOICES.find(v=>v.key==='ranking-0')!;
assert(rank.text.includes('Eleven v4 Turbo 和 Eleven v4'));
assert(rank.text.includes('AA 原生音色榜前二'));
assert.notEqual(assets[reader.key].voice,assets[rank.key].voice);
const main=fs.readFileSync(new URL('../src/Main.tsx',import.meta.url),'utf8');
assert(!main.includes('CAPTIONS.map'),'成片不应烧录第二层字幕');
console.log(`PASS：8镜头连续，${TOTAL/FPS}秒；${VOICES.length}段真实人声无截尾；BGM/音效齐全；没有重复烧录字幕。`);
