import React,{useEffect,useMemo,useState} from 'react';
import {Building2,Search,ExternalLink,Layers} from 'lucide-react';
import {SourceInsights} from './SourceInsights.jsx';
import {Pager} from './WorkspaceParts.jsx';
const PAGE_SIZE=5;
function checkedTime(value){if(!value)return '尚未检查';const date=new Date(value);return Number.isNaN(date.getTime())?'时间待确认':new Intl.DateTimeFormat('zh-CN',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(date)}
function statusTone(status){return ({'正常':'normal','延迟':'delayed','失败':'failed','未接入':'inactive'})[status]||'inactive'}
export function SourcesPage({sites,subscriptions,pending,onFollow,mode}){
 const [query,setQuery]=useState(''),[type,setType]=useState(''),[scope,setScope]=useState('all'),[status,setStatus]=useState(''),[page,setPage]=useState(0);
 const types=useMemo(()=>[...new Set(sites.map(s=>s.type))],[sites]);
 const statuses=useMemo(()=>[...new Set(sites.map(s=>s.status))],[sites]);
 const items=sites.filter(s=>s.name.includes(query.trim())&&(!type||s.type===type)&&(!status||s.status===status)&&(scope==='all'||subscriptions.sources.includes(s.id)));
 useEffect(()=>{setPage(p=>Math.min(p,Math.max(0,Math.ceil(items.length/PAGE_SIZE)-1)))},[items.length]);
 function change(setter,value){setter(value);setPage(0)}
 return <>
  <div className="workspace-heading"><div><h2>通知来源</h2><p>浏览校园单位，关注与你相关的信息来源。</p></div><span className="workspace-hint">{sites.length} 个来源 · 已关注 {subscriptions.sources.length} 个</span></div>
  <div className="source-directory">
   <aside className="source-categories"><h3>单位分类</h3><nav aria-label="来源类型">{['',...types].map(t=><button key={t} aria-pressed={type===t} onClick={()=>change(setType,t)}><span>{t?<Building2 size={15}/>:<Layers size={15}/>} {t||'全部来源'}</span><small>{t?sites.filter(s=>s.type===t).length:sites.length}</small></button>)}</nav><p>关注单位后，相关内容会优先展示。</p></aside>
   <section className="source-results" aria-label="来源目录"><div className="source-toolbar"><label className="directory-search"><Search size={14}/><input aria-label="查找来源" placeholder="搜索学院或部门" value={query} onChange={e=>change(setQuery,e.target.value)}/></label><div className="workspace-segment" aria-label="关注范围"><button aria-pressed={scope==='all'} onClick={()=>change(setScope,'all')}>全部</button><button aria-pressed={scope==='following'} onClick={()=>change(setScope,'following')}>已关注</button></div><select aria-label="采集状态" value={status} onChange={e=>change(setStatus,e.target.value)}><option value="">全部状态</option>{statuses.map(s=><option key={s}>{s}</option>)}</select></div>
    <div className="source-table" role="table" aria-label="网站来源与采集状态"><div className="source-table-head" role="row"><span role="columnheader">来源单位</span><span role="columnheader">采集状态</span><span role="columnheader">最近检查</span><span role="columnheader">关注</span></div>
     {items.slice(page*PAGE_SIZE,page*PAGE_SIZE+PAGE_SIZE).map(s=><div key={s.id} className="source-table-row" role="row"><div role="cell" className="source-unit"><span className="unit-mark"><Building2 size={17}/></span><div className="unit-identity"><strong title={s.name}>{s.url?<a href={s.url} target="_blank" rel="noreferrer">{s.name}<ExternalLink size={11}/></a>:s.name}</strong><small>{s.type}</small></div></div><div role="cell"><span className={`collection-state ${statusTone(s.status)}`} title={s.error||s.status}><i/>{s.status}</span></div><time role="cell" title={s.lastChecked||'尚未检查'}>{checkedTime(s.lastChecked)}</time><div role="cell"><button disabled={pending} className={`source-follow ${subscriptions.sources.includes(s.id)?'is-following':''}`} aria-pressed={subscriptions.sources.includes(s.id)} onClick={()=>onFollow(s.id)}>{subscriptions.sources.includes(s.id)?'已关注':'关注'}</button></div></div>)}
     {!items.length&&<div className="directory-empty"><Search size={24}/><p>没有符合条件的来源</p><button className="secondary" onClick={()=>{setQuery('');setType('');setStatus('');setScope('all');setPage(0)}}>清空筛选</button></div>}
    </div><Pager page={page} total={items.length} size={PAGE_SIZE} onChange={setPage}/>
   </section>
   <SourceInsights sites={sites} subscriptions={subscriptions}/>
  </div>
 </>;
}
