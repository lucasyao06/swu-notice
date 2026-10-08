import {useEffect,useMemo,useRef,useState} from 'react';
import {createCalendarRepository} from '../data/calendarRepository.js';
export function useCalendarData(mode){
 const repo=useMemo(()=>createCalendarRepository(mode),[mode]),current=useRef(repo);current.current=repo;
 const [state,setState]=useState({repo:null,items:[],lists:[]}),[error,setError]=useState(''),[loading,setLoading]=useState(true),[pending,setPending]=useState(false),[revision,setRevision]=useState(0),[now,setNow]=useState(Date.now());
 const locked=useRef(false),generation=useRef(0);
 useEffect(()=>{
  // Mutations schedule a fresh read on completion. A read begun during a write
  // could otherwise replace the mutation result with an older server snapshot.
  if(locked.current)return;
  const c=new AbortController(),version=++generation.current;
  const active=()=>!c.signal.aborted&&current.current===repo&&version===generation.current;
  setLoading(true);setError('');
  Promise.all([repo.list(c.signal),repo.lists(c.signal)]).then(([items,lists])=>{if(active())setState({repo,items,lists})}).catch(e=>{if(active())setError(e.message)}).finally(()=>{if(active())setLoading(false)});
  return()=>c.abort();
 },[repo,revision]);
 useEffect(()=>{const update=()=>{setNow(Date.now());if(document.visibilityState==='visible')setRevision(v=>v+1)};const timer=setInterval(update,30000);window.addEventListener('focus',update);document.addEventListener('visibilitychange',update);return()=>{clearInterval(timer);window.removeEventListener('focus',update);document.removeEventListener('visibilitychange',update)}},[]);
 async function change(kind,patch,id){
  if(locked.current)return null;
  locked.current=true;generation.current+=1;setPending(true);setError('');
  let succeeded=false;
  try{
   const result=await ({save:()=>repo.save(patch,id),remove:()=>repo.remove(id),saveList:()=>repo.saveList(patch,id),removeList:()=>repo.removeList(id)})[kind]();
   if(current.current!==repo)return null;
   generation.current+=1;
   setState(previous=>{
    const state=previous.repo===repo?previous:{repo,items:[],lists:[]};
    if(kind==='remove')return {...state,items:state.items.filter(e=>e.id!==id)};
    if(kind==='saveList')return {...state,lists:[...state.lists.filter(list=>list.id!==result.id),result]};
    if(kind==='removeList')return {...state,lists:state.lists.filter(list=>list.id!==id),items:state.items.map(event=>event.list_id===id?{...event,list_id:null}:event)};
    const {next_event:nextEvent,...event}=result;
    const additions=nextEvent?[event,nextEvent]:[event];
    return {...state,items:[...state.items.filter(item=>!additions.some(addition=>addition.id===item.id)),...additions]};
   });
   succeeded=true;setNow(Date.now());return result||true;
  }catch(e){if(current.current===repo)setError(e.message);return null}
  finally{
   locked.current=false;setPending(false);setLoading(false);
   if(succeeded||current.current!==repo)setRevision(v=>v+1);
  }
 }
 const items=state.repo===repo?state.items:[],lists=state.repo===repo?state.lists:[];
 return {items,lists,error,loading,pending,save:(patch,id)=>change('save',patch,id),remove:id=>change('remove',null,id),saveList:(patch,id)=>change('saveList',patch,id),removeList:id=>change('removeList',null,id),refresh:()=>setRevision(v=>v+1),due:items.filter(e=>!e.completed&&!e.reminded&&e.remind_at&&Date.parse(e.remind_at)<=now).sort((a,b)=>a.remind_at.localeCompare(b.remind_at))};
}
