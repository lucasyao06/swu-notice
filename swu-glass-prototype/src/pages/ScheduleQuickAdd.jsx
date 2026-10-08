import React,{useEffect,useRef,useState} from 'react';
import {Plus,CalendarDays} from 'lucide-react';
import {blankEvent} from '../data/calendarRepository.js';
import {shiftDate} from '../data/schedule.js';

export function ScheduleQuickAdd({contextKey,defaults,today,pending,loading,onSave,onAdded,hidden}){
 const [title,setTitle]=useState(''),[date,setDate]=useState(defaults.date),[custom,setCustom]=useState(false),input=useRef(null),saving=useRef(false);
 useEffect(()=>{setDate(defaults.date);setCustom(false)},[contextKey,defaults.date,defaults.list_id]);
 async function submit(e){
  e.preventDefault();const text=title.trim();if(!text||pending||loading||saving.current)return;
  saving.current=true;
  try{
   const result=await onSave({...blankEvent(date),...defaults,date,title:text});
   if(result){setTitle('');onAdded(text);input.current?.focus({preventScroll:true})}
  }finally{saving.current=false}
 }
 const tomorrow=shiftDate(today,1);
 return <form hidden={hidden} className="schedule-quick-add" aria-label="快速录入日程" onSubmit={submit}>
  <div className="quick-title-row"><Plus size={17}/><input ref={input} aria-label="快速添加任务" placeholder="添加任务，按 Enter 保存" maxLength={200} readOnly={pending} value={title} onChange={e=>setTitle(e.target.value)}/><button className="quick-submit" disabled={!title.trim()||pending||loading} type="submit">{pending?'保存中…':'添加'}</button></div>
  <div className="quick-date-row"><CalendarDays size={14}/>{[['','未安排'],[today,'今天'],[tomorrow,'明天']].map(([value,label])=><button key={label} type="button" disabled={pending} aria-pressed={!custom&&date===value} onClick={()=>{setDate(value);setCustom(false)}}>{label}</button>)}<button type="button" disabled={pending} aria-pressed={custom} onClick={()=>setCustom(true)}>选择日期</button>{custom&&<input aria-label="快速录入日期" type="date" disabled={pending} value={date} onChange={e=>setDate(e.target.value)}/>}</div>
 </form>;
}
