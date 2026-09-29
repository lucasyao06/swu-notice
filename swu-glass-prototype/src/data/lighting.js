export const LIGHTING_LABELS={morning:'柔和晨光',day:'通透日间',sunset:'暖金夕阳',moonlight:'银蓝月光'};
export function lightingPreference(value){return value==='auto'||Object.hasOwn(LIGHTING_LABELS,value)?value:'auto'}
export function resolveLighting(preference,now=new Date()){
 const mode=lightingPreference(preference);
 if(mode!=='auto')return mode;
 const hour=now.getHours();
 return hour>=5&&hour<10?'morning':hour>=10&&hour<17?'day':hour>=17&&hour<19?'sunset':'moonlight';
}
export function greetingAt(now){const hour=now.getHours();return hour<5?'夜深了，同学':hour<10?'早上好，同学':hour<12?'上午好，同学':hour<14?'中午好，同学':hour<17?'下午好，同学':hour<19?'傍晚好，同学':'晚上好，同学'}
