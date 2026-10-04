import React,{useEffect,useId,useRef,useState} from 'react';
import {Check,ChevronDown,Search} from 'lucide-react';

export function CollegeSelect({colleges,value,onChange}){
 const [open,setOpen]=useState(false),[query,setQuery]=useState(''),[active,setActive]=useState(0);
 const root=useRef(null),trigger=useRef(null),input=useRef(null),listId=useId();
 const selected=colleges?.find(x=>x.id===value);
 const matches=(colleges||[]).filter(x=>x.name.normalize('NFKC').includes(query.trim().normalize('NFKC')));
 function close(restore=false){setOpen(false);setQuery('');if(restore)trigger.current?.focus()}
 function show(){setQuery('');setActive(Math.max(0,(colleges||[]).findIndex(x=>x.id===value)));setOpen(true)}
 function choose(item){if(!item)return;close(true);if(item.id!==value)onChange(item.id)}
 useEffect(()=>{if(!open)return;input.current?.focus();const outside=e=>{if(!root.current?.contains(e.target))close()};document.addEventListener('pointerdown',outside);return()=>document.removeEventListener('pointerdown',outside)},[open]);
 useEffect(()=>{if(open)root.current?.querySelector('[data-active="true"]')?.scrollIntoView({block:'nearest'})},[open,active,query]);
 function keys(e){
  if(e.nativeEvent.isComposing)return;
  if(e.key==='Escape'){e.preventDefault();e.stopPropagation();close(true)}
  else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();setActive(i=>matches.length?(i+(e.key==='ArrowDown'?1:-1)+matches.length)%matches.length:0)}
  else if(e.key==='Enter'){e.preventDefault();choose(matches[active])}
 }
 return <div className="college-select" ref={root} onBlur={e=>{if(!e.currentTarget.contains(e.relatedTarget))close()}}>
  <span className="college-select-label">选择学院</span>
  <button ref={trigger} type="button" aria-label="选择学院" aria-haspopup="listbox" aria-expanded={open} aria-controls={open?listId:undefined} disabled={!colleges?.length} onClick={()=>open?close():show()} onKeyDown={e=>{if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();show()}}} className="college-select-trigger">{selected?.name||'正在加载学院…'}<ChevronDown size={15}/></button>
  {open&&<div className="college-select-popover"><div className="college-select-search"><Search size={15}/><input ref={input} role="combobox" aria-label="搜索学院" aria-autocomplete="list" aria-expanded="true" aria-controls={listId} aria-activedescendant={matches[active]?`${listId}-${matches[active].id}`:undefined} autoComplete="off" placeholder="搜索学院" value={query} onChange={e=>{setQuery(e.target.value);setActive(0)}} onKeyDown={keys}/></div>
   <div id={listId} role="listbox" aria-label="学院" className="college-select-options">{matches.map((item,index)=><div key={item.id} id={`${listId}-${item.id}`} role="option" aria-selected={item.id===value} data-active={index===active} className="college-select-option" onPointerDown={e=>e.preventDefault()} onClick={()=>choose(item)}>{item.name}{item.id===value&&<Check size={15}/>}</div>)}{!matches.length&&<p role="status">没有匹配的学院</p>}</div>
  </div>}
 </div>
}
