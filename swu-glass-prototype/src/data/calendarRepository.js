import {createHttpClient} from './httpClient.js';
export const localDate=(date=new Date())=>`${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;
export function blankEvent(date=localDate()){return {title:'',category:'other',location:'',date,time:'',end_time:'',notes:'',priority:'normal',reminder_minutes:null,timezone_offset:-new Date().getTimezoneOffset(),source_url:'',list_id:null,subtasks:[],repeat:'none',repeat_until:''}}
export function eventPayload(event){return Object.fromEntries(Object.keys(blankEvent()).map(k=>[k,event[k]??blankEvent()[k]]))}
const normalize=event=>({...blankEvent(''),completed:false,reminded:false,...event});
function reminder(event){return !event.date||event.reminder_minutes===null?null:new Date(Date.parse(`${event.date}T${event.time||'09:00'}:00Z`)-(event.timezone_offset+event.reminder_minutes)*60000).toISOString()}
function nextDate(event){
 const date=new Date(`${event.date}T12:00:00`);
 if(event.repeat==='monthly'){const day=date.getDate();date.setDate(1);date.setMonth(date.getMonth()+1);date.setDate(Math.min(day,new Date(date.getFullYear(),date.getMonth()+1,0).getDate()))}
 else date.setDate(date.getDate()+(event.repeat==='weekly'?7:1));
 return localDate(date);
}
export function createCalendarRepository(mode,request=createHttpClient()){
 if(mode==='live')return {
  list:signal=>request('/calendar/events',{signal}).then(r=>r.items.map(normalize)),
  save:(event,id)=>request(`/calendar/events${id?'/'+id:''}`,{method:id?'PATCH':'POST',body:event}).then(result=>({...normalize(result),...(result.next_event?{next_event:normalize(result.next_event)}:{})})),
  remove:id=>request(`/calendar/events/${id}`,{method:'DELETE'}),
  lists:signal=>request('/calendar/lists',{signal}).then(r=>r.items),
  saveList:(patch,id)=>request(`/calendar/lists${id?'/'+id:''}`,{method:id?'PATCH':'POST',body:patch}),
  removeList:id=>request(`/calendar/lists/${id}`,{method:'DELETE'}),
 };
 let items=[],lists=[],next=1,nextList=1;const generated=new Set();
 return {
  async list(){return structuredClone(items)},
  async lists(){return structuredClone(lists)},
  async saveList(patch,id){
   const previous=lists.find(list=>list.id===id);if(id&&!previous)throw Error('清单不存在');
   const list={color:'blue',...previous,...patch,id:id||nextList++};list.name=list.name?.trim();
   if(!list.name)throw Error('请输入清单名称');if(!['blue','teal','purple','orange','gray'].includes(list.color))throw Error('清单颜色无效');
   lists=id?lists.map(entry=>entry.id===id?list:entry):[...lists,list];return structuredClone(list);
  },
  async removeList(id){lists=lists.filter(list=>list.id!==id);items=items.map(event=>event.list_id===id?{...event,list_id:null}:event)},
  async save(patch,id){
   const previous=items.find(e=>e.id===id);if(id&&!previous)throw Error('日程不存在');
   const event=normalize({...previous,...structuredClone(patch),id:id||next++});
   if(event.list_id!==null&&!lists.some(list=>list.id===event.list_id))throw Error('清单不存在');
   if(!event.date){event.time='';event.end_time='';event.reminder_minutes=null;event.repeat='none';event.repeat_until=''}
   if(!id||['date','time','reminder_minutes','timezone_offset'].some(k=>k in patch&&patch[k]!==previous[k])){event.reminded=false;event.remind_at=reminder(event)}
   items=id?items.map(e=>e.id===id?event:e):[...items,event];
   let nextEvent;
   if(previous&&!previous.completed&&event.completed&&event.repeat!=='none'&&event.date&&!generated.has(id)){
    const date=nextDate(event);
    if(!event.repeat_until||date<=event.repeat_until){
     nextEvent={...event,id:next++,date,completed:false,reminded:false,subtasks:event.subtasks.map(step=>({...step,completed:false}))};
     nextEvent.remind_at=reminder(nextEvent);items.push(nextEvent);generated.add(id);
    }
   }
   return structuredClone({...event,...(nextEvent?{next_event:nextEvent}:{})});
  },
  async remove(id){items=items.filter(e=>e.id!==id)},
 };
}
