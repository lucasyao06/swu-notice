import {useEffect,useMemo,useRef,useState} from 'react';
import {createLiveRepository,createDemoRepository} from '../data/repository.js';
const empty={sites:[],subscriptions:{sources:[],keywords:[],categories:[],inApp:true},messages:[],unread:0};
export function useNoticeData({mode,query,tab,page,source,category}){
 const repo=useMemo(()=>mode==='demo'?createDemoRepository():createLiveRepository(),[mode]);
 const current=useRef(repo);current.current=repo;
 const [base,setBase]=useState({repo:null,...empty}),[listing,setListing]=useState({repo:null,items:[],total:0}),[home,setHome]=useState({repo:null,priority:[],latest:[],recentUpdates:[]});
 const [revision,setRevision]=useState(0),[error,setError]=useState(''),[loading,setLoading]=useState(true),[pending,setPending]=useState(false);
 const lock=useRef(false);
 useEffect(()=>{
  const controller=new AbortController();setError('');
  Promise.all([repo.bootstrap(controller.signal),repo.listNotices({size:2},controller.signal),repo.listNotices({tab:'subscribed',size:3},controller.signal)]).then(([b,l,p])=>{if(!controller.signal.aborted){setBase({repo,...b});setHome({repo,latest:l.items,priority:p.items.slice(0,2),recentUpdates:p.items})}}).catch(e=>{if(!controller.signal.aborted)setError(e.message)});
  return()=>controller.abort();
 },[repo,revision]);
 useEffect(()=>{
  const controller=new AbortController();setLoading(true);setError('');
  repo.listNotices({q:query,tab,page,source,category},controller.signal).then(result=>{if(!controller.signal.aborted)setListing({repo,...result})}).catch(e=>{if(!controller.signal.aborted){setListing({repo,items:[],total:0});setError(e.message)}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});
  return()=>controller.abort();
 },[repo,query,tab,page,source,category,revision]);
 useEffect(()=>{const timer=setInterval(()=>{if(document.visibilityState==='visible')setRevision(v=>v+1)},60000);return()=>clearInterval(timer)},[repo]);
 async function mutate(work){
  if(lock.current)return null;lock.current=true;setPending(true);setError('');
  try{const result=await work(repo);if(current.current!==repo)return null;setRevision(v=>v+1);return result??true}
  catch(e){if(current.current===repo)setError(e.message);return null}
  finally{lock.current=false;setPending(false)}
 }
 return {...(base.repo===repo?base:empty),...(listing.repo===repo?listing:{items:[],total:0}),...(home.repo===repo?home:{priority:[],latest:[],recentUpdates:[]}),ready:base.repo===repo,loading:loading||base.repo!==repo&&!error,error,pending,
  refresh:()=>setRevision(v=>v+1),saveSubscriptions:s=>mutate(r=>r.saveSubscriptions(s)),
  favorite:n=>mutate(r=>r.updateNotice(n.id,{favorite:!n.favorite})),
  readDetails:n=>mutate(async r=>{
   const notice=n.read?n:await r.updateNotice(n.id,{read:true});
   const related=base.repo===repo?base.messages.filter(m=>m.noticeId===n.id&&!m.read):[];
   for(const message of related)await r.readMessage(message.id);
   return notice;
  }),
  readMessage:id=>mutate(r=>r.readMessage(id)),
  async getNotice(id){try{const result=await repo.getNotice(id);return current.current===repo?result:null}catch(e){if(current.current===repo)setError(e.message);return null}},
 };
}
