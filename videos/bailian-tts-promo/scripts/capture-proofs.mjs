const fs=await import('node:fs/promises');
const root='/Users/yangguandao/Projects/legdonkey-plugins/videos/bailian-tts-promo';const p=(await taskSpace(179)).page('p1');
await p.cdp('Emulation.setDeviceMetricsOverride',{width:1920,height:1080,deviceScaleFactor:4,mobile:false});
await p.goto('http://127.0.0.1:4318/?capture=proof#clone');await p.setInputFiles('#cFile',[`${root}/public/audio/demo-recording.wav`]);await p.waitForSelector('#c-grade.on');
async function take(name,selector,range=false){
 await p.evaluate(async()=>{await document.fonts.ready});await p.waitForTimeout(650);
 const b=await p.evaluate(({selector,range})=>{const e=document.querySelector(selector);let r;if(range){const a=document.createRange();a.selectNodeContents(e);r=a.getBoundingClientRect()}else r=e.getBoundingClientRect();return{x:r.x+scrollX-4,y:r.y+scrollY-4,width:r.width+8,height:r.height+8}},{selector,range});
 const s=await p.cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{...b,scale:1}});await fs.writeFile(`${root}/public/textures/remake/${name}.png`,Buffer.from(s.data,'base64'));console.log(name,b);
}
await take('proof-pass','#cVerdictWord',true);await take('proof-submit','#cCloneBtn');
await p.evaluate(()=>{document.querySelector('#c-grade').classList.remove('on');document.querySelector('#c-done').classList.add('on');});await take('proof-saved','#cDoneMark');
