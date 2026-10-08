import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {CalendarDays,Clock,Bell,MapPin,Tag,List,Flag,Repeat,PlusCircle,Trash2,X,ExternalLink,ChevronDown} from 'lucide-react';
import {EVENT_TYPES,formatReminderTime} from '../data/schedule.js';
const reminders=[[0,'开始时提醒'],[5,'提前 5 分钟提醒'],[15,'提前 15 分钟提醒'],[30,'提前 30 分钟提醒'],[60,'提前 1 小时提醒'],[1440,'提前 1 天提醒']];
export function ScheduleEditor({draft,anchor,field,setDraft,pending,loading,save,onClose,onDelete,deleting,error,lists=[],quiet}){
 const ref=useRef(null),animation=useRef(null),closing=useRef(false),[timeOpen,setTimeOpen]=useState(false);
 useLayoutEffect(()=>{
  const el=ref.current,previous=document.activeElement;el.showModal();
  function position(){const width=Math.min(390,window.innerWidth-24);el.style.width=`${width}px`;const bottom=20,height=Math.min(el.scrollHeight,window.innerHeight-bottom-20),x=anchor?(anchor.right+12+width<=innerWidth?anchor.right+12:anchor.left-width-12):(innerWidth-width)/2,y=anchor?anchor.top:(innerHeight-height)/2;el.style.left=`${Math.max(12,Math.min(innerWidth-width-12,x))}px`;el.style.top=`${Math.max(20,Math.min(innerHeight-height-bottom,y))}px`;el.style.transformOrigin=anchor&&x<anchor.left?'right top':'left top'}
  position();if(!quiet)animation.current=el.animate([{opacity:0,transform:'translateY(8px) scale(.97)'},{opacity:1,transform:'translateY(0) scale(1)'}],{duration:220,easing:'cubic-bezier(.22,1,.36,1)'});
  const observer=new ResizeObserver(position);observer.observe(el);window.addEventListener('resize',position);
  return()=>{animation.current?.cancel();observer.disconnect();window.removeEventListener('resize',position);el.close();if(previous?.isConnected)previous.focus({preventScroll:true})};
 },[]);
 useEffect(()=>{if(quiet)animation.current?.cancel()},[quiet]);
 function close(){if(pending||closing.current)return;if(quiet){onClose();return}closing.current=true;animation.current?.cancel();animation.current=ref.current.animate([{opacity:1,transform:'translateY(0) scale(1)'},{opacity:0,transform:'translateY(5px) scale(.985)'}],{duration:150,easing:'ease-in'});animation.current.onfinish=onClose}
 const subtasks=draft.subtasks||[];
 function changeDate(date){setDraft(d=>({...d,date,...(!date?{time:'',end_time:'',repeat:'none',repeat_until:'',reminder_minutes:null}:{timezone_offset:-new Date(`${date}T${d.time||'09:00'}`).getTimezoneOffset()})}))}
 function subtask(id,patch){field('subtasks',subtasks.map(t=>t.id===id?{...t,...patch}:t))}
 return <dialog ref={ref} className="schedule-editor" aria-label={draft.id?'编辑日程':'新建日程'} onCancel={e=>{e.preventDefault();close()}}><form className="event-form" onSubmit={save}>
 <header><label className="editor-completion"><input type="checkbox" aria-label="日程已完成" disabled={pending} checked={Boolean(draft.completed)} onChange={e=>field('completed',e.target.checked)}/><span className="sr-only">日程已完成</span></label><button type="button" className="icon-button" aria-label="取消编辑" disabled={pending} onClick={close}><X size={19}/></button></header>
 <fieldset disabled={pending}>
 <label className="editor-title"><span className="sr-only">日程标题</span><input autoFocus required maxLength={200} value={draft.title} onChange={e=>field('title',e.target.value)} placeholder="准备做什么？"/></label>
 <div className="editor-metadata">
 <div className="editor-date-row"><label className="editor-info-row"><CalendarDays size={19}/><span className="sr-only">日期</span><input type="date" aria-label="日期" value={draft.date} onChange={e=>changeDate(e.target.value)}/></label><button type="button" className="text-button" disabled={!draft.date} aria-label="清除日期" onClick={()=>changeDate('')}>未安排</button></div>
 <label className="editor-info-row"><List size={19}/><span className="sr-only">清单</span><select aria-label="所属清单" value={draft.list_id??''} onChange={e=>field('list_id',e.target.value?Number(e.target.value):null)}><option value="">收集箱</option>{lists.map(l=><option value={l.id} key={l.id}>{l.name}</option>)}</select></label>
 <label className="editor-info-row"><Flag size={19}/><span className="sr-only">优先级</span><select aria-label="优先级" value={draft.priority} onChange={e=>field('priority',e.target.value)}><option value="high">高优先级</option><option value="normal">普通优先级</option><option value="low">低优先级</option></select></label>
 <button type="button" className="editor-info-row" aria-label="调整日程时间" aria-expanded={timeOpen} onClick={()=>setTimeOpen(v=>!v)}><Clock size={19}/><span>{draft.date?(draft.time?`${draft.time}${draft.end_time?' – '+draft.end_time:''}`:'全天'):'设置日期后安排时间'}<small className="row-action">调整</small></span></button>
 <label className="editor-info-row"><Bell size={19}/><span className="sr-only">提醒</span><select aria-label="提醒" disabled={!draft.date} value={draft.reminder_minutes??'none'} onChange={e=>field('reminder_minutes',e.target.value==='none'?null:Number(e.target.value))}><option value="none">不提醒</option>{reminders.map(([v,t])=><option key={v} value={v}>{t}</option>)}</select></label>
 {draft.reminder_minutes!=null&&<div className="editor-property-hint"><span>提醒时间：{formatReminderTime(draft)}</span><small>网页打开时提醒{!draft.time?' · 全天日程以 09:00 为准':''}</small></div>}
 <label className="editor-info-row"><Repeat size={19}/><span className="sr-only">重复</span><select aria-label="重复规则" disabled={!draft.date} value={draft.repeat||'none'} onChange={e=>setDraft(d=>({...d,repeat:e.target.value,repeat_until:e.target.value==='none'?'':d.repeat_until||''}))}><option value="none">不重复</option><option value="daily">每天</option><option value="weekly">每周</option><option value="monthly">每月</option></select></label>
 {draft.repeat&&draft.repeat!=='none'&&<div className="editor-repeat-fields"><label>重复截止<input type="date" min={draft.date} value={draft.repeat_until||''} onChange={e=>field('repeat_until',e.target.value)}/></label><small className="reminder-hint">完成后安排下一次</small></div>}
 <label className="editor-info-row"><MapPin size={19}/><span className="sr-only">地点</span><input aria-label="地点" maxLength={200} value={draft.location||''} onChange={e=>field('location',e.target.value)} placeholder="添加地点"/></label>
 <label className="editor-info-row"><Tag size={19}/><span className="sr-only">分类</span><select aria-label="日程分类" value={draft.category||'other'} onChange={e=>field('category',e.target.value)}>{Object.entries(EVENT_TYPES).map(([id,label])=><option value={id} key={id}>{label}</option>)}</select></label>
 </div>
 <details open={timeOpen} onToggle={e=>setTimeOpen(e.currentTarget.open)}><summary>时间安排<ChevronDown size={14}/></summary><div className="editor-time-fields">
 <label className="all-day"><input type="checkbox" disabled={!draft.date} checked={!draft.time} onChange={e=>setDraft(d=>({...d,time:e.target.checked?'':'09:00',end_time:''}))}/>全天</label>
 {draft.time&&<div className="event-two"><label>开始时间<input type="time" required value={draft.time} onChange={e=>field('time',e.target.value)}/></label><label>结束时间<input type="time" value={draft.end_time} onChange={e=>field('end_time',e.target.value)}/></label></div>}
 </div></details>
 <label className="editor-notes"><List size={19}/><span className="sr-only">备注</span><textarea rows={2} maxLength={4000} value={draft.notes} onChange={e=>field('notes',e.target.value)} placeholder="添加描述…"/></label>
 <div className="subtask-list">{subtasks.map((t,i)=><div key={t.id}><input type="checkbox" aria-label={`完成子任务 ${i+1}`} checked={t.completed} onChange={e=>subtask(t.id,{completed:e.target.checked})}/><input aria-label={`子任务 ${i+1}`} maxLength={200} value={t.title} onChange={e=>subtask(t.id,{title:e.target.value})} placeholder="子任务"/><button type="button" aria-label={`删除子任务 ${i+1}`} onClick={()=>field('subtasks',subtasks.filter(x=>x.id!==t.id))}><X size={14}/></button></div>)}<button className="add-subtask" type="button" disabled={subtasks.length>=100} onClick={()=>field('subtasks',[...subtasks,{id:crypto.randomUUID(),title:'',completed:false}])}><PlusCircle size={20}/>添加子任务</button></div>
 {draft.source_url&&<a className="event-source" href={draft.source_url} target="_blank" rel="noreferrer">查看关联通知 <ExternalLink size={12}/></a>}
 </fieldset>{error&&<p className="error-text" role="alert">{error}</p>}<div className="event-actions">{draft.id&&<button type="button" className="delete-event" disabled={pending} onClick={onDelete}><Trash2 size={14}/>{deleting?'确认删除':'删除'}</button>}<button className="primary" disabled={pending||loading}>{pending?'保存中…':'保存日程'}</button></div>
 </form></dialog>
}
