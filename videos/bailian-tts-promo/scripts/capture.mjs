// 通过 ego-browser nodejs 运行，使用已创建的唯一任务空间。
const fs = await import('node:fs/promises');
const root = '/Users/yangguandao/Projects/legdonkey-plugins/videos/bailian-tts-promo';
const t = await taskSpace(178), p = t.page('p1');
await p.cdp('Emulation.setDeviceMetricsOverride', {width:1920,height:1080,deviceScaleFactor:2,mobile:false});
const layout = {};
async function capture(name, selectors) {
  await p.evaluate(async()=>{await document.fonts.ready;});
  await p.waitForTimeout(650);
  const info = await p.evaluate((selectors)=>({pageH:document.documentElement.scrollHeight,elements:Object.fromEntries(selectors.map(s=>{const r=document.querySelector(s).getBoundingClientRect();return [s,{x:r.x+scrollX,y:r.y+scrollY,w:r.width,h:r.height}]}))}),selectors);
  layout[name]=info;
  const full=await p.cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:0,y:0,width:1920,height:info.pageH,scale:1}});
  await fs.writeFile(`${root}/public/textures/${name}.png`,Buffer.from(full.data,'base64'));
  for (const [selector,r] of Object.entries(info.elements)) {
    const shot=await p.cdp('Page.captureScreenshot',{format:'png',captureBeyondViewport:true,clip:{x:r.x,y:r.y,width:r.w,height:r.h,scale:1}});
    await fs.writeFile(`${root}/public/textures/${name}-${selector.replace(/[^a-zA-Z]/g,'')}.png`,Buffer.from(shot.data,'base64'));
  }
}
await p.goto('http://127.0.0.1:4318/?capture=voices#voices');
await p.waitForSelector('#vName');
await capture('voices',['aside[aria-label="试听台"]','#vList']);
await p.goto('http://127.0.0.1:4318/?capture=clone#clone');
await capture('clone',['#c-read']);
// 仅加载本片已生成的合成音频作本地质检样例，不录麦克风，不提交云端复刻。
await p.setInputFiles('#cFile',[`${root}/public/audio/demo-recording.wav`]);
await p.waitForSelector('#c-grade.on');
// 录音质检的公开演示状态；不把文件导入的“未检测”冒充真实测量。
await p.evaluate(()=>{
  document.querySelector('#cGradeSource').textContent='状态演示 · 非真实录音';
  const rows=document.querySelectorAll('#cRows tr');
  ['合适','没有'].forEach((value,i)=>{
    rows[i+1].querySelector('.val').textContent=value;
    const mark=rows[i+1].querySelector('.mark');mark.className='mark pass';mark.textContent='合格';
    rows[i+1].querySelector('.hint')?.remove();
  });
});
await capture('grade',['#c-grade']);
await fs.writeFile(`${root}/public/textures/layout.json`,JSON.stringify(layout,null,2));
console.log(layout);
