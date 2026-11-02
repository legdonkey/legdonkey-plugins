const fs=await import('node:fs/promises');
const root='/Users/yangguandao/Projects/legdonkey-plugins/videos/bailian-tts-promo', dest=`${root}/public/textures/remake`;
await fs.mkdir(dest,{recursive:true});
const p=(await taskSpace(179)).page('p1');
await p.cdp('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:2,mobile:false});
const layouts={};
async function shot(name,selector){
 await p.evaluate(async()=>{await document.fonts.ready});await p.waitForTimeout(650);
 const box=await p.evaluate(sel=>{const e=document.querySelector(sel),r=e.getBoundingClientRect();return{x:r.x+scrollX,y:r.y+scrollY,width:r.width,height:r.height}},selector);
 const data=await p.cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{...box,scale:1}});
 await fs.writeFile(`${dest}/${name}.png`,Buffer.from(data.data,'base64'));layouts[name]=box;
}
await p.goto('https://artificialanalysis.ai/text-to-speech/leaderboard/provider-voice');
await p.waitForSelector('table tbody tr');
const aa=await p.evaluate(()=>{const rows=[...document.querySelectorAll('table tr')].slice(0,3),a=rows[0].getBoundingClientRect(),b=rows[2].getBoundingClientRect();return{box:{x:a.x+scrollX,y:a.y+scrollY,width:a.width,height:b.bottom-a.top},text:rows.map(x=>x.innerText)}});
const aaPng=await p.cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{...aa.box,scale:1}});
await fs.writeFile(`${dest}/aa-top2.png`,Buffer.from(aaPng.data,'base64'));await fs.writeFile(`${root}/reference/aa-snapshot.json`,JSON.stringify({url:await p.url(),checked:'2026-11-02',...aa},null,2));layouts.aa=aa.box;
const manifest=JSON.parse(await fs.readFile(`${root}/public/audio/demos/manifest.json`,'utf8'));
for(const [i,item] of manifest.segments.entries()){
 await p.goto(`http://127.0.0.1:4318/?capture=voice-${i}#voices`);
 await p.waitForSelector('#vText');await p.fill('#vText','让想法，被听见。');await p.fill('#vInstr',item.instruction);
 await p.fill('#vQ',item.voice);await p.click(`#vList [data-voice="${item.voice}"]`);
 await p.click('#vListen');await p.waitForFunction(()=>document.querySelector('#vAudio').duration>0);
 await p.evaluate(()=>{const a=document.querySelector('#vAudio');a.pause();a.currentTime=.35;window.scrollTo(0,0)});
 await shot(`voice-${i}`,'aside[aria-label="试听台"]');
}
await p.goto('http://127.0.0.1:4318/?capture=clone-remake#clone');
await shot('clone-ready','#c-read');
await p.evaluate(()=>{document.body.classList.add('recording');document.querySelector('#cClock').textContent='00:12.4';document.querySelector('#cDue').textContent='可以停了';document.querySelector('#cLv').style.transform='scaleX(.72)';document.querySelector('#cLvSay').textContent='合适';document.querySelector('#cMeter').dataset.state='ok';document.querySelector('#cRecBtn span').textContent='停止';});
await shot('clone-record','#pg-clone');
await p.evaluate(()=>document.body.classList.remove('recording'));
await p.setInputFiles('#cFile',[`${root}/public/audio/demo-recording.wav`]);await p.waitForSelector('#c-grade.on');
await p.evaluate(()=>{document.querySelector('#cGradeSource').textContent='流程演示 · 非真实录音';const rows=document.querySelectorAll('#cRows tr');['合适','没有'].forEach((s,i)=>{rows[i+1].querySelector('.val').textContent=s;const m=rows[i+1].querySelector('.mark');m.className='mark pass';m.textContent='合格';rows[i+1].querySelector('.hint')?.remove()});});
await shot('clone-grade','#c-grade');
await p.evaluate(()=>{document.querySelector('#c-grade').classList.remove('on');document.querySelector('#c-done').classList.add('on');document.querySelector('#cDoneText').textContent='声音已收藏，下次配音就能使用。';document.querySelector('#cDoneVid').textContent='演示音色 · 非真实账号';});
await shot('clone-done','#c-done');
await fs.writeFile(`${dest}/layout.json`,JSON.stringify(layouts,null,2));console.log(layouts);
