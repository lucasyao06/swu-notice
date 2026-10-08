import React,{useEffect,useId,useRef,useState} from 'react';
import {House,Bell,CalendarDays,Star,Grid2X2,GraduationCap,Settings} from 'lucide-react';
import {dockInfluence} from '../data/dockMotion.js';
const entries=[[House,'首页','home'],[Bell,'通知','notices'],[CalendarDays,'日程','calendar'],[Star,'订阅','subscriptions'],[Grid2X2,'来源','sources'],[GraduationCap,'赛事','competitions'],[Settings,'设置','settings']];
export function Dock({active,onNavigate,quiet,children}){
 const [expanded,setExpanded]=useState(false),id=useId();
 const shell=useRef(null),handle=useRef(null),host=useRef(null),frame=useRef(null),pointer=useRef(null),keyboardFocus=useRef(false),touch=useRef(false);
 function reset(){cancelAnimationFrame(frame.current);pointer.current=null;host.current?.querySelectorAll('button').forEach(button=>button.style.removeProperty('--dock-influence'))}
 useEffect(()=>{if(quiet||!expanded)reset();return()=>cancelAnimationFrame(frame.current)},[quiet,expanded]);
 useEffect(()=>{
  if(!expanded)return;
  const dismiss=event=>{if(!shell.current?.contains(event.target)){keyboardFocus.current=false;setExpanded(false)}};
  document.addEventListener('pointerdown',dismiss,true);
  return()=>document.removeEventListener('pointerdown',dismiss,true);
 },[expanded]);
 function follow(event){
  if(quiet||event.pointerType!=='mouse')return;
  pointer.current=event.clientX;cancelAnimationFrame(frame.current);
  frame.current=requestAnimationFrame(()=>host.current?.querySelectorAll('button').forEach(button=>{
   const box=button.getBoundingClientRect();button.style.setProperty('--dock-influence',dockInfluence(pointer.current-box.left-box.width/2));
  }));
 }
 function dismissWithKeyboard(event){
  if(event.key!=='Escape')return;
  event.preventDefault();event.stopPropagation();handle.current?.focus();keyboardFocus.current=false;setExpanded(false);reset();
 }
 return <div className={`dock-reveal ${expanded?'is-expanded':''}`} data-page={active} ref={shell}
  onPointerEnter={event=>{if(event.pointerType==='mouse')setExpanded(true)}}
  onPointerLeave={event=>{if(event.pointerType==='mouse'){reset();if(!keyboardFocus.current)setExpanded(false)}}}
  onPointerDownCapture={event=>{touch.current=event.pointerType==='touch';keyboardFocus.current=false}}
  onFocusCapture={event=>{keyboardFocus.current=event.target.matches(':focus-visible');setExpanded(true)}}
  onBlurCapture={event=>{if(!event.currentTarget.contains(event.relatedTarget)){keyboardFocus.current=false;setExpanded(false)}}}
  onKeyDown={dismissWithKeyboard}>
  <button className="dock-handle" ref={handle} aria-label="展开导航栏" aria-controls={id} aria-expanded={expanded} onClick={()=>setExpanded(true)}><span aria-hidden="true"/></button>
  <nav className="dock" id={id} aria-label="主导航" aria-hidden={!expanded} inert={!expanded} ref={host} onPointerMove={follow} onPointerLeave={reset}>
   {children?.(host,!expanded)}{entries.map(([Icon,name,key])=><button key={key} className={active===key?'active':''} aria-current={active===key?'page':undefined} onClick={()=>{onNavigate(key);if(touch.current){setExpanded(false);reset()}}} onFocus={event=>{if(!quiet)event.currentTarget.style.setProperty('--dock-influence',1)}} onBlur={reset}><span className="dock-item"><Icon size={25} strokeWidth={1.75}/><span>{name}</span></span></button>)}
  </nav>
 </div>;
}
