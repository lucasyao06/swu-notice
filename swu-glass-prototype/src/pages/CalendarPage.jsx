import React,{useEffect,useLayoutEffect,useRef,useState} from 'react';
import {ChevronLeft,ChevronRight,Plus,CalendarDays,Clock,Inbox,BookOpen,GraduationCap,Users,Bell,Search,CalendarRange,AlertCircle,Layers,SlidersHorizontal} from 'lucide-react';
import {blankEvent,eventPayload,localDate} from '../data/calendarRepository.js';
import {ScheduleEditor} from './ScheduleEditor.jsx';
import {ScheduleWeek} from './ScheduleWeek.jsx';
import {ScheduleList} from './ScheduleList.jsx';
import {ScheduleQuickAdd} from './ScheduleQuickAdd.jsx';
import {EVENT_TYPES,weekDates,shiftDate,quickTaskDefaults} from '../data/schedule.js';
const NAV=[['inbox','收集箱',Inbox],['today','今天',CalendarDays],['upcoming','最近 7 天',Clock],['all','全部日程',CalendarRange],['unscheduled','未安排',CalendarDays],['overdue','逾期',AlertCircle]];
const TYPE_ICONS={study:BookOpen,work:GraduationCap,activity:Users,personal:Bell,other:Layers};
const PRIORITY={high:'高优先级',normal:'普通',low:'低优先级'};
const initialView=()=>matchMedia('(max-width:600px)').matches?'day':'week';
export function CalendarPage({calendar,request,onRequestConsumed,quiet,onFeedback=()=>{}}){
 const today=localDate();
 const [selected,setSelected]=useState(today),[month,setMonth]=useState(today.slice(0,7)),[filter,setFilter]=useState('all'),[query,setQuery]=useState(''),[draft,setDraft]=useState(null),[validation,setValidation]=useState(''),[deleting,setDeleting]=useState(false);
 const [viewMode,setViewMode]=useState(initialView),[allViewMode,setAllViewMode]=useState(initialView),[category,setCategory]=useState(''),[range,setRange]=useState('all'),[anchor,setAnchor]=useState(null),[listId,setListId]=useState(null),[listDraft,setListDraft]=useState(null),[navExpanded,setNavExpanded]=useState(false),[revealDate,setRevealDate]=useState(0);
 const weekScroll=useRef(null),scopeStrip=useRef(null);
 const [completionDrafts,setCompletionDrafts]=useState({});
 const {items:storedItems,error,loading,pending}=calendar;
 const items=storedItems.map(event=>Object.hasOwn(completionDrafts,event.id)?{...event,completed:completionDrafts[event.id]}:event);
 useLayoutEffect(()=>{
  function revealScope(){
   if(innerWidth>999)return;
   const strip=scopeStrip.current,active=strip?.querySelector('[aria-pressed="true"]');if(!active)return;
   const viewport=strip.getBoundingClientRect(),button=active.getBoundingClientRect();
   if(button.left<viewport.left)strip.scrollLeft+=button.left-viewport.left;
   else if(button.right>viewport.right)strip.scrollLeft+=button.right-viewport.right;
  }
  revealScope();window.addEventListener('resize',revealScope);return()=>window.removeEventListener('resize',revealScope);
 },[range,listId]);
 useEffect(()=>{if(request){const event=request.id?request:{...blankEvent(),...request};if(event.date){setSelected(event.date);setMonth(event.date.slice(0,7));setRevealDate(v=>v+1)}setDraft(event);setValidation('');setDeleting(false);onRequestConsumed()}},[request]);
 function edit(event,position=null){setAnchor(position);setDraft({...blankEvent(event.date),...event});setValidation('');setDeleting(false)}
 function selectDate(date){setSelected(date);setMonth(date.slice(0,7))}
 function moveDate(amount){
  if(viewMode==='day'||viewMode==='week'){selectDate(shiftDate(selected,amount*(viewMode==='week'?7:1)));return}
  const [y,m]=month.split('-').map(Number);setMonth(localDate(new Date(y,m-1+amount,1)).slice(0,7));
 }
 function goToday(){selectDate(today);setRange('all');setListId(null);setRevealDate(v=>v+1)}
 function clearFilters(){setQuery('');setFilter('all');setCategory('')}
 function feedback(result){const next=result.next_event;onFeedback(next?`已完成，下次安排：${Number(next.date.slice(5,7))}月${Number(next.date.slice(-2))}日`:'已完成日程')}
 async function complete(patch,id){
  if(pending)return null;
  setCompletionDrafts(current=>({...current,[id]:patch.completed}));
  try{const result=await calendar.save(patch,id);if(result&&patch.completed)feedback(result);return result}
  finally{setCompletionDrafts(current=>{const next={...current};delete next[id];return next})}
 }
 const [year,m]=month.split('-').map(Number),start=new Date(year,m-1,1),offset=(start.getDay()+6)%7;
 const days=Array.from({length:42},(_,i)=>localDate(new Date(year,m-1,1-offset+i))),future=shiftDate(today,6);
 const inRange=e=>range==='inbox'?!e.list_id:range==='unscheduled'?!e.date:range==='all'||(range==='today'?e.date===today:range==='upcoming'?e.date>=today&&e.date<=future:Boolean(e.date)&&e.date<today&&!e.completed);
 const matches=items.filter(e=>(listId===null||e.list_id===listId)&&(!category||(e.category||'other')===category)&&inRange(e)&&(!query||`${e.title} ${e.notes}`.toLowerCase().includes(query.toLowerCase()))&&(filter==='all'||(filter==='done'?e.completed:!e.completed)));
 const dayItems=matches.filter(e=>e.date===selected).sort((a,b)=>Number(a.completed)-Number(b.completed)||(a.time||'').localeCompare(b.time||'')||({high:0,normal:1,low:2}[a.priority]-{high:0,normal:1,low:2}[b.priority]));
 const filtered=Boolean(query||category||filter!=='all'),defaults=quickTaskDefaults({range,today,listId,category});
 const newEvent=()=>edit({...blankEvent(range==='today'?today:range==='inbox'||range==='unscheduled'?'':selected),list_id:listId,category:category||'other'});
 async function save(e){
  e.preventDefault();if(!draft.title.trim()){setValidation('请填写日程标题');return}
  if(draft.end_time&&(!draft.time||draft.end_time<=draft.time)){setValidation('结束时间须晚于开始时间');return}
  if((draft.subtasks||[]).some(t=>!t.title.trim())){setValidation('请填写子任务标题');return}
  const date=draft.date?new Date(`${draft.date}T${draft.time||'09:00'}`):new Date(),previous=items.find(t=>t.id===draft.id);
  const result=await calendar.save({...eventPayload(draft),completed:Boolean(draft.completed),title:draft.title.trim(),timezone_offset:-date.getTimezoneOffset()},draft.id);
  if(result){if(result.date)selectDate(result.date);setDraft(null);if(draft.completed&&!previous?.completed)feedback(result);else onFeedback('日程已保存')}
 }
 function field(name,value){setDraft(d=>({...d,[name]:value}));setValidation('')}
 return <>
  {error&&!draft&&<div className='calendar-error' role='alert'>{error}<button onClick={calendar.refresh}>重试</button></div>}
  <div className={`calendar-layout schedule-layout view-${viewMode}`}>
   <aside className='schedule-nav' aria-label='日程导航'>
    <div className='schedule-scopes' ref={scopeStrip}>{NAV.map(([id,label,Icon])=><button className='scope-nav' key={id} aria-pressed={range===id&&listId===null} onClick={()=>{setRange(id);setListId(null);setViewMode(id==='all'?allViewMode:'list')}}><Icon size={20}/>{label}</button>)}</div>
    <button className='schedule-nav-toggle' aria-expanded={navExpanded} onClick={()=>setNavExpanded(v=>!v)}><SlidersHorizontal size={16}/>筛选</button>
    <div className={`schedule-extra ${navExpanded?'expanded':''}`}>
     <div className='list-nav-heading'><h3>我的清单</h3><button aria-label='新建清单' onClick={()=>{setNavExpanded(true);setListDraft({name:'',color:'blue'})}}><Plus size={13}/></button></div>
     {(calendar.lists||[]).map(l=><div className='custom-list-nav' key={l.id}><button aria-pressed={listId===l.id} onClick={()=>{setListId(l.id);setRange('all');setViewMode('list')}}><i className={`list-color-${l.color}`}/><span>{l.name}</span><small>{items.filter(e=>e.list_id===l.id&&!e.completed).length}</small></button><button aria-label={`编辑清单：${l.name}`} onClick={()=>setListDraft({...l})}>⋯</button></div>)}
     {listDraft&&<form className='list-edit-form' onSubmit={async e=>{e.preventDefault();if(await calendar.saveList({name:listDraft.name.trim(),color:listDraft.color},listDraft.id))setListDraft(null)}}><input aria-label='清单名称' required maxLength={60} placeholder='清单名称' value={listDraft.name} onChange={e=>setListDraft(d=>({...d,name:e.target.value}))}/><select aria-label='清单颜色' value={listDraft.color} onChange={e=>setListDraft(d=>({...d,color:e.target.value}))}>{[['blue','蓝色'],['teal','青色'],['purple','紫色'],['orange','橙色'],['gray','灰色']].map(([id,t])=><option key={id} value={id}>{t}</option>)}</select><div><button disabled={pending} type='submit'>保存</button><button type='button' onClick={()=>setListDraft(null)}>取消</button>{listDraft.id&&<button disabled={pending} type='button' onClick={async()=>{if(!listDraft.confirm){setListDraft(d=>({...d,confirm:true}));return}if(await calendar.removeList(listDraft.id)){if(listId===listDraft.id)setListId(null);setListDraft(null)}}}>{listDraft.confirm?'确认移除':'移除'}</button>}</div>{listDraft.confirm&&<small>任务会移至收集箱</small>}</form>}
     <h3 className='category-heading'>分类</h3><button className='category-reset' aria-pressed={!category} onClick={()=>setCategory('')}>全部分类<span>{items.length}</span></button>
     {Object.entries(EVENT_TYPES).map(([id,label])=>{const Icon=TYPE_ICONS[id];return <button className={`category-nav type-${id}`} key={id} aria-pressed={category===id} onClick={()=>setCategory(id)}><Icon size={21}/>{label}<span>{items.filter(e=>(e.category||'other')===id).length}</span></button>})}
     <div className='unscheduled-preview'><h3>未安排</h3>{items.filter(e=>!e.date&&!e.completed).slice(0,3).map(e=><div key={e.id}><input type='checkbox' aria-label={`完成未安排任务：${e.title}`} disabled={pending} checked={e.completed} onChange={()=>complete({completed:!e.completed},e.id)}/><button onClick={()=>edit(e)}>{e.title}</button></div>)}{!items.some(e=>!e.date&&!e.completed)&&<p>暂时没有未安排任务</p>}</div>
    </div>
   </aside>
   <header className='schedule-header'><div className='calendar-toolbar'>
    <div className='schedule-title'><h2>日程</h2><h3>{viewMode==='list'?'日程清单':viewMode==='day'?`${Number(selected.slice(5,7))}月${Number(selected.slice(-2))}日`:`${year}年${m}月`}</h3></div>
    <div className='month-nav'><button disabled={viewMode==='list'} aria-label={viewMode==='day'?'前一天':viewMode==='week'?'上一周':'上个月'} onClick={()=>moveDate(-1)}><ChevronLeft size={19}/></button><button className='calendar-today' onClick={goToday}>今天</button><button disabled={viewMode==='list'} aria-label={viewMode==='day'?'后一天':viewMode==='week'?'下一周':'下个月'} onClick={()=>moveDate(1)}><ChevronRight size={19}/></button></div>
    {viewMode==='week'&&<span className='week-range'>{weekDates(selected).map(d=>`${Number(d.slice(5,7))}月${Number(d.slice(-2))}日`).filter((_,i)=>i===0||i===6).join(' – ')}</span>}
    <div className='schedule-filterbar'><label><Search size={14}/><input aria-label='搜索所有日程' placeholder='搜索日程' value={query} onChange={e=>setQuery(e.target.value)}/></label><select aria-label='日程状态筛选' value={filter} onChange={e=>setFilter(e.target.value)}><option value='all'>全部状态</option><option value='todo'>未完成</option><option value='done'>已完成</option></select><span>{items.filter(e=>!e.completed&&e.date===today).length} 项今日待办</span></div>
    <div className='schedule-tools'><div className='workspace-segment' aria-label='日程视图切换'>{[['day','日'],['week','周'],['month','月'],['list','清单']].map(([id,label])=><button key={id} aria-pressed={viewMode===id} onClick={()=>{setViewMode(id);if((range==='all'&&listId===null)||id!=='list')setAllViewMode(id);if(id!=='list')setRange('all')}}>{label}</button>)}</div><button className='primary' disabled={pending||loading} onClick={newEvent}><Plus size={18}/>新建日程</button></div>
   </div></header>
   <section className='month-panel schedule-main' aria-label='日程视图'>
    <ScheduleQuickAdd hidden={viewMode!=='list'} contextKey={`${range}:${listId??''}`} defaults={defaults} today={today} pending={pending} loading={loading} onSave={calendar.save} onAdded={title=>onFeedback(`已添加：${title}`)}/>
    {viewMode==='week'||viewMode==='day'?<ScheduleWeek view={viewMode} revealDate={revealDate} initialScrollTop={weekScroll.current} onScrollChange={value=>{weekScroll.current=value}} selected={selected} items={matches} draft={draft} onSelect={selectDate} onEdit={edit} onMove={calendar.save} onComplete={complete} pending={pending}/>:viewMode==='list'?<ScheduleList items={matches} onEdit={edit} onComplete={complete} pending={pending} loading={loading} filtered={filtered} onClear={clearFilters} onAdd={newEvent}/>:<>
     <div className='weekdays'>{['一','二','三','四','五','六','日'].map(d=><span key={d}>{d}</span>)}</div>
     <div className='month-grid'>{days.map(date=>{const tasks=matches.filter(e=>e.date===date);return <button key={date} className={`calendar-day ${date.slice(0,7)!==month?'other-month':''} ${date===selected?'selected':''} ${date===today?'today':''}`} aria-label={`${date}，${tasks.length} 项日程`} aria-pressed={date===selected} onClick={()=>selectDate(date)}><span className='day-number'>{Number(date.slice(-2))}</span><div className='day-events'>{tasks.slice(0,2).map(t=><span title={t.title} key={t.id} className={`type-${t.category||'other'} ${t.completed?'completed':''}`}>{t.priority!=='normal'&&<b className={`task-priority ${t.priority}`} aria-label={PRIORITY[t.priority]}>{t.priority==='high'?'!':'↓'}</b>}{t.title}</span>)}{tasks.length>2&&<small>+{tasks.length-2} 项</small>}</div></button>})}</div>
    </>}
    <div className='calendar-key'>{Object.entries(EVENT_TYPES).map(([id,label])=><span key={id}><i className={`type-${id}`} style={{background:'var(--event-accent)'}}/>{label}</span>)}{loading&&<span role='status'>正在加载日程…</span>}</div>
   </section>
   {viewMode==='month'&&<section className='agenda-panel' aria-label='当天日程'>
    <header className='agenda-heading'><div><h3>{Number(selected.slice(5,7))} 月 {Number(selected.slice(-2))} 日</h3><span>{dayItems.length} 项日程</span></div><button className='icon-button' aria-label='添加当天日程' disabled={pending||loading} onClick={newEvent}><Plus size={18}/></button></header>
    <div className='agenda-items'>{dayItems.map(event=><div className={`agenda-item ${event.completed?'is-complete':''}`} key={event.id}><input type='checkbox' aria-label={`完成日程：${event.title}`} checked={event.completed} disabled={pending} onChange={()=>complete({completed:!event.completed},event.id)}/><button onClick={()=>edit(event)}><strong><span className={`agenda-category-dot type-${event.category||'other'}`}/>{event.title}</strong><small><Clock size={11}/>{event.time?`${event.time}${event.end_time?'–'+event.end_time:''}`:'全天'}<span className={`event-priority ${event.priority}`}>{PRIORITY[event.priority]}</span></small>{event.notes&&<p>{event.notes}</p>}</button></div>)}{!dayItems.length&&<div className='calendar-empty'><CalendarDays size={28}/><p>{loading?'正在加载…':filtered?'没有匹配的日程':'这一天还没有安排'}</p>{!loading&&<button className='text-button' disabled={pending} onClick={filtered?clearFilters:newEvent}>{filtered?'清除筛选':'添加日程'} <Plus size={12}/></button>}</div>}</div>
   </section>}
  </div>
  {draft&&<ScheduleEditor quiet={quiet} draft={draft} anchor={anchor} field={field} setDraft={setDraft} pending={pending} loading={loading} save={save} onClose={()=>setDraft(null)} onDelete={async()=>{if(!deleting){setDeleting(true);return}if(await calendar.remove(draft.id)){setDraft(null);onFeedback('日程已删除')}}} deleting={deleting} error={validation||error} lists={calendar.lists||[]}/>}
 </>;
}
