import React, {useState,useRef,useEffect} from 'react';
import LiquidGlass from 'liquid-glass-react';
import {Search,Sun,Moon,Sunset,Sunrise,CalendarDays,Bell,UserRound,ChevronDown,ChevronRight,ArrowRight,Star,Sparkles,GraduationCap,Monitor,Globe,BookOpen,FileText,Users,House,Grid2X2,Settings,SlidersHorizontal,Clock,Bookmark,Check,X,Building2,Mail,CheckCheck,Heart,MessageCircle,Folder,Quote} from 'lucide-react';

import {useLighting} from './hooks/useLighting.js';
import {AmbientLight} from './components/AmbientLight.jsx';
import {readPreference,writePreference} from './data/preferences.js';
import {useNoticeData} from './hooks/useNoticeData.js';
import {showReadingState} from './data/reading.js';
import {CATEGORIES} from './data/adapters.js';
import {SubscriptionsPage,SourcesPage,SettingsPage,Pager} from './pages/WorkspacePages.jsx';

function DateCard({onOpen,quiet}) {
 const host=useRef(null);
 const [now,setNow]=useState(()=>new Date());
 useEffect(()=>{const timer=setInterval(()=>setNow(new Date()),60000);return()=>clearInterval(timer)},[]);
 const options={timeZone:'Asia/Shanghai'};
 const date=new Intl.DateTimeFormat('zh-CN',{...options,month:'long',day:'numeric'}).format(now);
 const weekday=new Intl.DateTimeFormat('zh-CN',{...options,weekday:'long'}).format(now);
 const parts=new Intl.DateTimeFormat('zh-CN-u-ca-chinese',{...options,month:'long',day:'numeric'}).formatToParts(now);
 const day=Number(parts.find(p=>p.type==='day')?.value);
 const digits=['一','二','三','四','五','六','七','八','九'];
 const lunarDay=day===10?'初十':day===20?'二十':day===30?'三十':day<10?'初'+digits[day-1]:day<20?'十'+digits[day-11]:'廿'+digits[day-21];
 return <button className="date-card glass liquid-panel" ref={host} aria-label="打开日历" onClick={onOpen}>
  <Lens host={host} quiet={quiet} radius={18} subtle/>
  <span className="date-card-heading"><time>{date} · {weekday}</time><CalendarDays size={16}/></span>
  <span className="date-card-lunar">农历{parts.find(p=>p.type==='month')?.value}{lunarDay}</span>
 </button>
}
function Lens({host,quiet,radius=40,subtle=false}) {
 return <span className="lens" aria-hidden="true"><LiquidGlass className="lens-surface" padding="0" cornerRadius={radius} displacementScale={subtle?12:22} blurAmount={.015} saturation={110} aberrationIntensity={subtle?.2:.5} elasticity={quiet?0:subtle?.025:.12} mode="standard" mouseContainer={host} globalMousePos={quiet?{x:0,y:0}:undefined} mouseOffset={quiet?{x:0,y:0}:undefined} style={{position:'absolute',width:'100%',height:'100%',left:'50%',top:'50%'}}><span /></LiquidGlass></span>
}
function GlassPanel({className,quiet,children}) {
 const host=useRef(null);
 return <section ref={host} className={`glass liquid-panel ${className}`}><Lens host={host} quiet={quiet} radius={20} subtle/>{children}</section>
}
function Notice({item,favorites,onFavorite,onOpen,large=false,pending=false,showRead=false}) {
 const Icon=item.Icon||({'教学教务':GraduationCap,'学术讲座':Monitor,'国际交流':Globe,'校园服务':BookOpen}[item.category]||FileText);
 return <article className={`notice ${large?'notice-large':''}`}>
  <span className={`unit-icon ${item.tone}`}><Icon size={large?27:23} strokeWidth={1.7}/></span>
  <div className="notice-copy"><div className="notice-heading"><button className="notice-title" disabled={pending} onClick={()=>onOpen(item)}>{item.title}</button>{large&&item.badge&&<span className={`tag relation relation-${item.id}`}>{item.id===1?<Heart size={11}/>:<Check size={11}/>} {item.badge}</span>}{!large&&<span className={`tag ${item.id===4?'purple':item.id===5?'orange':''}`}>{item.category}</span>}</div><p>{item.summary}</p><div className="metadata"><span>{item.source}</span><span className="meta-dot">·</span><time>{item.date}</time>{large&&<span className="tag category">{item.category}</span>}{showRead&&<span className="read-state">{item.read?'已读':'未读'}</span>}</div></div>
  <button className={`icon-button favorite ${favorites.includes(item.id)?'saved':''}`} aria-label={`${favorites.includes(item.id)?'取消收藏':'收藏'}：${item.title}`} aria-pressed={favorites.includes(item.id)} disabled={pending} onClick={()=>onFavorite(item.id)}><Star size={21}/></button>
  <button className="icon-button detail-arrow" disabled={pending} aria-label={`查看详情：${item.title}`} onClick={()=>onOpen(item)}><ChevronRight size={19}/></button>
 </article>
}
export function App(){
 const [view,setView]=useState('home'),[query,setQuery]=useState(''),[search,setSearch]=useState(''),[tab,setTab]=useState('all');
 const [mode,setModeState]=useState(()=>new URLSearchParams(location.search).get('mode')==='demo'?'demo':'live');
 const [page,setPage]=useState(0),[sourceFilter,setSourceFilter]=useState(''),[categoryFilter,setCategoryFilter]=useState('');
 const data=useNoticeData({mode,query:search,tab,page,source:sourceFilter,category:categoryFilter});
 const {sites:units,subscriptions,priority,latest,recentUpdates,items:filtered,total}=data;
 const {sources,keywords,categories:cats}=subscriptions;
 const visibleNotices=[...priority,...latest,...recentUpdates,...filtered];
 const favorites=visibleNotices.filter(n=>n.favorite).map(n=>n.id);
 const unread=data.unread;
 function setMode(value){const url=new URL(location.href);url.searchParams.set('mode',value);history.replaceState(null,'',url);setModeState(value);setPage(0);setSearch('');setQuery('');setTab('all');setSourceFilter('');setCategoryFilter('');setModal(null)}
 useEffect(()=>{setPage(0)},[search,tab,sourceFilter,categoryFilter]);
 const [modal,setModal]=useState(null),[toast,setToast]=useState('');
 const [motion,setMotion]=useState(()=>readPreference('motion',true)),[reduced,setReduced]=useState(matchMedia('(prefers-reduced-motion: reduce)').matches);
 const dialog=useRef(null),dock=useRef(null),searchRef=useRef(null),toastTimer=useRef(null),returnFocus=useRef(null);
 useEffect(()=>writePreference('motion',motion),[motion]);
 const {preference:daylight,setPreference:setDaylight,phase,now,greeting}=useLighting();
 const LightIcon=phase==='moonlight'?Moon:phase==='sunset'?Sunset:phase==='morning'?Sunrise:Sun;
 const quiet=!motion||reduced;
 const previousView=useRef(view);
 const modalAnimation=useRef(null);
 const transitionAnimation=useRef(null);
 useEffect(()=>{const m=matchMedia('(prefers-reduced-motion: reduce)');const f=()=>setReduced(m.matches);m.addEventListener('change',f);return()=>{m.removeEventListener('change',f);clearTimeout(toastTimer.current)}},[]);
 useEffect(()=>{
  modalAnimation.current?.cancel();
  const el=dialog.current;
  if(modal){
   if(!el.open){returnFocus.current=document.activeElement;el.showModal()}
   if(!quiet)modalAnimation.current=el.animate([{opacity:0,transform:'translateY(10px) scale(.98)'},{opacity:1,transform:'translateY(0) scale(1)'}],{duration:220,easing:'cubic-bezier(.22,1,.36,1)'});
  }else if(el.open){el.close();returnFocus.current?.focus()}
  return()=>modalAnimation.current?.cancel();
 },[modal,quiet]);
 function closeModal(){
  if(quiet){setModal(null);return}
  if(modalAnimation.current?.playState==='running'&&dialog.current.dataset.closing)return;
  modalAnimation.current?.cancel();
  const el=dialog.current;el.dataset.closing='true';
  const animation=el.animate([{opacity:1,transform:'translateY(0) scale(1)'},{opacity:0,transform:'translateY(6px) scale(.985)'}],{duration:150,easing:'ease-in'});
  modalAnimation.current=animation;
  animation.onfinish=()=>{delete el.dataset.closing;setModal(null)};
  animation.oncancel=()=>{delete el.dataset.closing};
 }
 useEffect(()=>{
  transitionAnimation.current?.cancel();
  const before=previousView.current;previousView.current=view;
  if(quiet||before===view)return;
  const target=document.querySelector('.content-grid');
  if(!target)return;
  const order=['home','notices','subscriptions','sources','settings'];
  const direction=order.indexOf(view)>order.indexOf(before)?1:-1;
  const animation=target.animate([{transform:`translateX(${direction*72}px)`,opacity:0},{transform:'translateX(0)',opacity:1}],{duration:320,easing:'cubic-bezier(.22,1,.36,1)'});
  transitionAnimation.current=animation;
  return()=>animation.cancel();
 },[view,quiet]);
 useEffect(()=>{
  if(quiet||view!=='notices')return;
  const target=document.querySelector('.notice-center .latest-list');
  const animation=target?.animate([{opacity:.3,transform:'translateY(5px)'},{opacity:1,transform:'translateY(0)'}],{duration:180,easing:'ease-out'});
  return()=>animation?.cancel();
 },[tab,search,quiet]);

 function tell(t){setToast(t);clearTimeout(toastTimer.current);toastTimer.current=setTimeout(()=>setToast(''),2600)}
 async function favorite(id){const item=visibleNotices.find(n=>n.id===id)||modal?.notice;if(!item)return;const result=await data.favorite(item);if(result){if(modal?.type==='notice')setModal(m=>m?.type==='notice'&&m.notice.id===result.id?{...m,notice:result}:m);tell(result.favorite?'已加入收藏':'已取消收藏')}}
 function openNotice(n){setModal({type:'notice',notice:n})}
 async function readDetails(n){
  if(!n.url||data.pending)return;
  const detail=window.open('about:blank','_blank');
  if(!detail){tell('请允许打开新窗口后重试');return}
  detail.opener=null;detail.location.href=n.url;
  const result=await data.readDetails(n);
  if(result)setModal(m=>m?.type==='notice'&&m.notice.id===n.id?{...m,notice:result}:m);
 }
 async function saveSubscriptions(value){const result=await data.saveSubscriptions(value);if(result)tell('订阅已保存');return result}
 async function follow(id){const selected=sources.includes(id);await saveSubscriptions({...subscriptions,sources:selected?sources.filter(x=>x!==id):[...sources,id]})}
 function manage(){nav('subscriptions')}
 function submit(e){e.preventDefault();setSearch(query.trim());setTab('all');setView('notices');window.scrollTo({top:0,behavior:'instant'})}
 function nav(id){
  
  setModal(null);setView(id);setPage(0);setSourceFilter('');setCategoryFilter('');setSearch('');setQuery('');setTab('all');window.scrollTo({top:0,behavior:'instant'});
 }

 const active=view;
 const isWorkspace=['subscriptions','sources','settings'].includes(view);
 const toggle=(arr,set,v)=>set(arr.includes(v)?arr.filter(x=>x!==v):[...arr,v]);
 const row=(n,large=false)=><Notice key={n.id} item={n} large={large} showRead={showReadingState(n,subscriptions)} pending={data.pending} favorites={favorites} onFavorite={favorite} onOpen={openNotice}/>;
 return <div className={`app ${view==='home'?'home-view':''} ${quiet?'still':''} light-${phase}`} >
 <div className="campus-scene" aria-hidden="true"/><AmbientLight phase={phase}/>
 <a className="skip" href="#content">跳转到通知</a>
 <header className="topbar"><div className="topbar-inner"><button className="brand" onClick={()=>nav('home')} aria-label="西南大学通知聚合平台首页"><img className="school-logo" src="/assets/swu-logo-horizontal.png" alt="西南大学 SOUTHWEST UNIVERSITY"/><span className="brand-rule"/><span className="product">通知聚合平台<small>SWU Notice</small></span></button>
 <form className="search-glass" ref={searchRef} onSubmit={submit}><Lens host={searchRef} quiet={quiet}/><Search size={21}/><input aria-label="搜索通知" placeholder="搜索通知标题、单位或关键词" value={query} onChange={e=>setQuery(e.target.value)}/>{query&&<button type="button" className="search-clear" aria-label="清空搜索" onClick={()=>{setQuery('');setSearch('')}}><X size={15}/></button>}<button className="sr-only" type="submit">搜索</button></form>
 <div className="profile"><select className="mode-select" aria-label="数据模式" disabled={data.pending} value={mode} onChange={e=>setMode(e.target.value)}><option value="live">真实数据</option><option value="demo">演示模式</option></select><LightIcon className={`sun phase-icon phase-${phase}`} size={29}/><div className="greeting"><strong>{greeting}</strong><small>{new Intl.DateTimeFormat('zh-CN',{month:'long',day:'numeric',weekday:'long'}).format(now)}</small></div><span className="profile-rule"/><button className="icon-button inbox" aria-label="消息提醒" onClick={()=>{setModal({type:'inbox'})}}><Bell size={23}/>{unread>0&&<b>{unread>99?'99+':unread}</b>}</button><button className="avatar" aria-label="个人设置" onClick={()=>nav('settings')}><UserRound size={24}/></button></div></div></header>
 <main className="page" id="content">{view==='home'&&<section className="hero"><div className="hero-photo"/><div className="hero-copy"><div className="eyebrow">校园资讯，与你有关</div><h1>重要通知，不再错过</h1><p>汇聚校园通知，让与你相关的信息先一步抵达。</p></div><div className="hero-motto">含弘光大<br/><span>继往开来</span></div><DateCard quiet={quiet} onOpen={()=>setModal({type:'calendar'})}/></section>}
 {data.error&&<div className="connection-error" role="alert">{data.error}<button onClick={data.refresh}>重试</button></div>}
 {data.loading&&<div className="loading-status" role="status">正在加载…</div>}
 {isWorkspace?<section className="content-grid workspace-page" aria-label={view==='subscriptions'?'订阅页面':view==='sources'?'来源页面':'设置页面'}>
 {view==='subscriptions'&&data.ready&&<SubscriptionsPage key={mode} sites={units} subscriptions={subscriptions} pending={data.pending} mode={mode} onSave={saveSubscriptions}/>}
 {view==='sources'&&<SourcesPage key={mode} sites={units} subscriptions={subscriptions} pending={data.pending} mode={mode} onFollow={follow}/>}
 {view==='settings'&&<SettingsPage motion={motion} setMotion={setMotion} daylight={daylight} setDaylight={setDaylight} phase={phase} reduced={reduced} mode={mode} setMode={setMode}/>}
 </section>:<div className="content-grid"><div className="main-column">
 {view==='home'?<><section className="glass panel priority"><div className="section-head"><div className="section-title"><Sparkles className="blue" size={25}/><h2>为你优先</h2><span>根据你的订阅，为你筛选</span></div><button className="text-button" onClick={()=>{setView('notices');setTab('subscribed')}}>查看全部 <ArrowRight size={16}/></button></div><div className="priority-list">{priority.length?priority.slice(0,2).map(n=>row(n,true)):<div className="empty"><Bookmark/><h3>还没有匹配的优先通知</h3><p>选择你关注的单位或分类，让相关信息先抵达。</p><button className="primary" onClick={manage}>设置我的订阅</button></div>}</div></section>
 <section className="glass panel latest"><div className="section-head"><div className="section-title"><Clock className="blue" size={25}/><h2>最新通知</h2><span>全校动态，及时掌握</span></div><button className="text-button" onClick={()=>nav('notices')}>查看全部 <ArrowRight size={16}/></button></div><div className="latest-list">{latest.map(n=>row(n))}{!latest.length&&!data.loading&&<div className="empty"><FileText/><h3>暂无通知</h3></div>}</div></section></>:
 <section className="glass panel notice-center"><div className="section-head"><div className="section-title"><Bell className="blue" size={24}/><h2>{search?'搜索结果':'通知中心'}</h2><span>{total.toLocaleString()} 条{mode==='demo'?'示例':''}通知</span></div><button className="text-button" onClick={()=>{setSearch('');setQuery('');setTab('all');setSourceFilter('');setCategoryFilter('');setPage(0)}}>重置筛选</button></div><div className="tabs">{[['all','全部通知'],['subscribed','我的订阅'],['saved','我的收藏']].map(([id,name])=><button key={id} className={tab===id?'selected':''} aria-pressed={tab===id} onClick={()=>setTab(id)}>{name}</button>)}</div><div className="notice-filters"><select aria-label="筛选单位" value={sourceFilter} onChange={e=>setSourceFilter(e.target.value)}><option value="">全部学院与部门</option>{units.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select><select aria-label="筛选分类" value={categoryFilter} onChange={e=>setCategoryFilter(e.target.value)}><option value="">全部分类</option>{CATEGORIES.map(c=><option key={c}>{c}</option>)}</select><button className="text-button" onClick={data.refresh}>刷新</button></div>{search&&<p className="results-label">关键词「{search}」的搜索结果</p>}<div className="latest-list">{filtered.length?filtered.map(n=>row(n,true)):<div className="empty"><Search/><h3>暂时没有找到相关通知</h3><p>试试其他关键词或筛选条件。</p><button className="secondary" onClick={()=>{setSearch('');setQuery('');setTab('all')}}>查看全部通知</button></div>}</div><Pager quickJump page={page} total={total} size={6} onChange={setPage}/></section>}
 </div><aside className="sidebar"><GlassPanel className="side-panel" quiet={quiet}><div className="section-head"><h2>我的订阅</h2><button className="text-button" onClick={manage}><Settings size={15}/> 管理</button></div><div className="subscription-inner">{[[UserRound,'关注单位',`${sources.length} 个`,'blue'],[MessageCircle,'订阅关键词',`${keywords.length} 个`,'cyan'],[Folder,'通知分类',`${cats.length} 类`,'violet']].map(([Icon,label,count,tone])=><button className="subscription-row" onClick={manage} key={label}><span className={`small-icon ${tone}`}><Icon size={21}/></span><strong>{label}</strong><span>{count}</span><ChevronRight size={16}/></button>)}<div className="subscription-tags"><small>常用订阅</small><div>{[...units.filter(u=>sources.includes(u.id)).slice(0,2).map(u=>u.name),...keywords.slice(0,1)].map(x=><button key={x} onClick={()=>{setQuery(x);setSearch(x);setTab('all');setView('notices')}}>{x.length>10?x.slice(0,8)+'…':x}</button>)}</div></div></div></GlassPanel>
 <GlassPanel className="side-panel updates" quiet={quiet}><div className="section-head"><h2>最近更新</h2><span className="muted">我的订阅</span></div><div className="timeline">{recentUpdates.map(n=><button key={n.id} onClick={()=>openNotice(n)}><i/><span title={n.title}>{n.title}</span><time>{n.dateVerified?n.date.slice(5,10):'待核验'}</time></button>)}{!recentUpdates.length&&<p className="muted">暂无订阅更新</p>}</div></GlassPanel>
 <section className="glass culture"><Quote size={34}/><blockquote>含弘光大，继往开来</blockquote><p>在西大，遇见更好的自己。</p><small>— SOUTHWEST UNIVERSITY</small></section></aside></div>}
 <footer aria-hidden="true"/></main>
 <nav className="dock" aria-label="主导航" ref={dock}><Lens host={dock} quiet={quiet}/>{[[House,'首页','home'],[Bell,'通知','notices'],[Star,'订阅','subscriptions'],[Grid2X2,'来源','sources'],[Settings,'设置','settings']].map(([Icon,name,id])=><button key={id} className={active===id?'active':''} aria-current={active===id?'page':undefined} onClick={()=>nav(id)}><Icon size={25} strokeWidth={1.65}/><span>{name}</span></button>)}</nav>
 <dialog aria-label="通知与偏好设置" ref={dialog} onCancel={e=>{e.preventDefault();closeModal()}} onClick={e=>{if(e.target===e.currentTarget)closeModal()}}><div className="dialog-content">{data.error&&<p className="error-text" role="alert">{data.error}</p>}<button className="dialog-close icon-button" aria-label="关闭弹窗" onClick={closeModal}><X size={22}/></button>{modal?.type==='notice'&&<><span className="tag">{modal.notice.isDemo?'示例通知':'原站通知'}</span><h2>{modal.notice.title}</h2><p className="dialog-meta">{modal.notice.source} · {modal.notice.date}</p><p className="dialog-summary">{modal.notice.summary}</p><div className="dialog-actions"><button disabled={data.pending} className="secondary" onClick={()=>favorite(modal.notice.id)}><Star size={17}/>{modal.notice.favorite?'取消收藏':'收藏通知'}</button><button className="primary" disabled={data.pending||!modal.notice.url} onClick={()=>readDetails(modal.notice)}>{modal.notice.url?'阅读详情':'详情暂不可用'} <ArrowRight size={17}/></button></div></>}
 {modal?.type==='calendar'&&<><span className="eyebrow">校园日历</span><h2>校园日历</h2><p className="dialog-summary">暂未开放</p><div className="dialog-actions"><button className="primary" onClick={closeModal}>知道了</button></div></>}
 {modal?.type==='inbox'&&<><span className="eyebrow">与你相关的动态</span><h2>消息提醒</h2><p className="muted">{data.unread} 条未读 · 最近 {Math.min(data.messages.length,20)} 条</p><div className="inbox-list">{data.messages.slice(0,20).map(m=><button key={m.id} disabled={data.pending} onClick={async()=>{const n=await data.getNotice(m.noticeId);if(n)openNotice(n)}}><span className="small-icon blue"><Bell size={19}/></span><span><strong>{m.title}</strong><small>{m.source} · {m.status} · {m.read?'已读':'未读'}</small></span><ChevronRight size={18}/></button>)}{!data.messages.length&&<p className="muted">暂无推送消息</p>}</div></>}

 </div></dialog><div className={`toast ${toast?'visible':''}`} role="status" aria-live="polite"><Check size={17}/>{toast}</div>
 </div>
}
