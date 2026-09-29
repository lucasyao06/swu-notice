import React,{useEffect,useState} from 'react';
import {Building2,Search,Plus,Check,SlidersHorizontal,Bell} from 'lucide-react';
import {CATEGORIES} from '../data/adapters.js';
import {Pager} from './WorkspaceParts.jsx';
const PAGE_SIZE=4;
const normalizeKeywords=value=>[...new Set(value.split(/[、,，]/).map(x=>x.trim()).filter(Boolean))];
const signature=value=>JSON.stringify({...value,sources:[...value.sources].sort(),categories:[...value.categories].sort(),keywords:[...value.keywords].sort()});
export function SubscriptionsPage({sites,subscriptions,pending,onSave,mode}){
 const [draft,setDraft]=useState(()=>structuredClone(subscriptions)),[keywords,setKeywords]=useState(subscriptions.keywords.join('、'));
 const [query,setQuery]=useState(''),[scope,setScope]=useState('following'),[page,setPage]=useState(0),[validation,setValidation]=useState('');
 const value={...draft,keywords:normalizeKeywords(keywords)};
 const dirty=signature(value)!==signature(subscriptions);
 const matches=sites.filter(s=>s.name.includes(query.trim())&&(scope==='all'||draft.sources.includes(s.id)));
 useEffect(()=>{setPage(p=>Math.min(p,Math.max(0,Math.ceil(matches.length/PAGE_SIZE)-1)))},[matches.length]);
 function toggle(key,item){setDraft(s=>({...s,[key]:s[key].includes(item)?s[key].filter(x=>x!==item):[...s[key],item]}))}
 function reset(){setDraft(structuredClone(subscriptions));setKeywords(subscriptions.keywords.join('、'));setValidation('')}
 async function save(){if(value.sources.length>50||value.keywords.length>50||value.keywords.some(k=>k.length>50)){setValidation('单位和关键词各最多 50 项，每个关键词最多 50 字');return}setValidation('');const saved=await onSave(value);if(saved)setKeywords(value.keywords.join('、'))}
 return <>
  <div className="workspace-heading"><div><h2>管理我的订阅</h2><p>让关注的单位与感兴趣的内容，优先出现在你的首页。</p></div><span className={`edit-state ${dirty?'is-dirty':''}`}>{dirty?'有未保存的修改':'偏好已同步'}</span></div>
  <div className="subscriptions-layout">
   <section className="followed-section" aria-label="单位订阅">
    <div className="section-label"><h3><Building2 size={16}/> 关注单位</h3><span>{draft.sources.length} / 50</span></div>
    <div className="subscription-tools"><div className="workspace-segment" aria-label="单位范围"><button aria-pressed={scope==='following'} onClick={()=>{setScope('following');setPage(0)}}>已关注</button><button aria-pressed={scope==='all'} onClick={()=>{setScope('all');setPage(0)}}><Plus size={12}/> 添加单位</button></div><label className="directory-search"><Search size={14}/><input aria-label="查找订阅单位" placeholder="搜索学院或部门" value={query} onChange={e=>{setQuery(e.target.value);setPage(0)}}/></label></div>
    <div className="followed-units">{matches.slice(page*PAGE_SIZE,page*PAGE_SIZE+PAGE_SIZE).map(s=><label className="followed-unit" key={s.id}><span className="unit-mark"><Building2 size={17}/></span><span className="unit-identity"><strong title={s.name}>{s.name}</strong><small>{s.type}</small></span><input aria-label={s.name} type="checkbox" disabled={pending} checked={draft.sources.includes(s.id)} onChange={()=>toggle('sources',s.id)}/></label>)}{!matches.length&&<div className="directory-empty"><Building2 size={24}/><p>{query?'没有找到匹配的单位':scope==='following'?'还没有关注单位':'暂无来源单位'}</p>{scope==='following'&&<button className="secondary" onClick={()=>{setScope('all');setQuery('');setPage(0)}}>浏览全部单位</button>}</div>}</div>
    <Pager page={page} total={matches.length} size={PAGE_SIZE} onChange={setPage}/>
   </section>
   <section className="interest-section" aria-label="兴趣偏好"><div className="section-label"><h3><SlidersHorizontal size={16}/> 兴趣偏好</h3><span>满足任一条件即可匹配</span></div>
    <fieldset disabled={pending} className="interest-fields"><legend className="sr-only">订阅偏好</legend><div><h4>通知分类</h4><div className="category-picks">{CATEGORIES.map(c=><button key={c} type="button" aria-pressed={draft.categories.includes(c)} onClick={()=>toggle('categories',c)}>{draft.categories.includes(c)&&<Check size={12}/>} {c}</button>)}</div></div>
     <div className="keyword-editor"><label htmlFor="subscription-keywords">订阅关键词</label><textarea id="subscription-keywords" value={keywords} onChange={e=>setKeywords(e.target.value)} placeholder="例如：奖学金、人工智能、国际交流" rows={2}/><small>用顿号或逗号分隔，匹配通知标题与内容。</small></div>
     <div className="delivery-preference"><div><h4><Bell size={14}/> 站内推送</h4><small>新内容匹配订阅时接收提醒</small></div><label><input type="checkbox" aria-label="接收站内推送" checked={draft.inApp} onChange={e=>setDraft(d=>({...d,inApp:e.target.checked}))}/><span>{draft.inApp?'已开启':'已关闭'}</span></label></div>
    </fieldset>
   </section>
  </div>
  {validation&&<p role="alert" className="error-text">{validation}</p>}<div className="workspace-actions"><button disabled={pending||!dirty} className="secondary" onClick={reset}>重置修改</button><button disabled={pending} className="primary" onClick={save}>{pending?'保存中…':'保存订阅'}</button></div>
 </>;
}
