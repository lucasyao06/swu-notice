import {localDate} from './calendarRepository.js';
export const EVENT_TYPES={study:'学习',work:'工作',activity:'活动',personal:'个人',other:'其他'};
export const atDate=value=>new Date(`${value}T12:00:00`);
export function shiftDate(value,amount){const date=atDate(value);date.setDate(date.getDate()+amount);return localDate(date)}
export function quickTaskDefaults({range,today,listId=null,category=''}){return {date:range==='today'&&listId===null?today:'',list_id:listId,category:category||'other'}}
export function reminderDateTime(event){
 if(!event.date||event.reminder_minutes==null)return null;
 const offset=event.timezone_offset??-new Date(`${event.date}T${event.time||'09:00'}`).getTimezoneOffset();
 return new Date(Date.parse(`${event.date}T${event.time||'09:00'}:00Z`)-(offset+event.reminder_minutes)*60000);
}
export function formatReminderTime(event){const date=reminderDateTime(event);return date&&!Number.isNaN(date.getTime())?new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).format(date):''}
export function weekDates(selected){const start=atDate(selected),offset=(start.getDay()+6)%7;start.setDate(start.getDate()-offset);return Array.from({length:7},(_,i)=>{const d=new Date(start);d.setDate(d.getDate()+i);return localDate(d)})}
export const minutes=value=>{const [h,m]=value.split(':').map(Number);return h*60+m};
export const clock=value=>`${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`;
export function moveEvent(event,date,minute){const duration=event.end_time?minutes(event.end_time)-minutes(event.time):60;const start=Math.max(0,Math.min(1439-duration,Math.round(minute/15)*15));return {date,time:clock(start),end_time:clock(start+duration),timezone_offset:-new Date(`${date}T${clock(start)}`).getTimezoneOffset()}}
// Assign simultaneous events separate lanes, sharing widths within each overlap group.
export function eventLanes(events){const sorted=events.map(e=>({...e,start:minutes(e.time),end:e.end_time?minutes(e.end_time):Math.min(1440,minutes(e.time)+60)})).sort((a,b)=>a.start-b.start||a.id-b.id);let group=[],groupEnd=-1;const output=[];function finish(){const ends=[];for(const e of group){let lane=ends.findIndex(end=>end<=e.start);if(lane<0)lane=ends.length;ends[lane]=e.end;e.lane=lane}output.push(...group.map(e=>({...e,lanes:ends.length})));group=[]}for(const e of sorted){if(e.start>=groupEnd){finish();groupEnd=-1}group.push(e);groupEnd=Math.max(groupEnd,e.end)}finish();return output}
