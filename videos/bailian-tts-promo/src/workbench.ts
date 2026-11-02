import {Main,SCENES,C} from './Main';
import {SHOTS,SFX,VOICES,BGM,TOTAL,FPS} from './timeline';
const TITLES:Record<string,string>={hook:'先听，再说。',models:'选对模型',ranking:'排名前二，也在你的工作台。',outro:'bailian-tts'};
export const WORKBENCH={
 name:'百炼配音 · 听见亮点',revision:'remake-1',fps:FPS,width:1920,height:1080,total:TOTAL,background:C.room,
 shots:SHOTS.map((s,i)=>({id:s.id,label:s.label,from:s.from,duration:s.duration,component:SCENES[i],props:{duration:s.duration,...(TITLES[s.id]?{title:TITLES[s.id]}:{})},schema:TITLES[s.id]?[{type:'text',key:'title',label:'主文案',default:TITLES[s.id]}]:[],durationProp:'duration'})),
 captions:[],transitions:[],overlays:[],sfx:[...VOICES,...SFX],bgm:[BGM],original:Main,
};
