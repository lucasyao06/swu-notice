import {createHttpClient} from './httpClient.js';
import {noticeFromApi,siteFromApi,subscriptionFromApi,subscriptionToApi,messageFromApi} from './adapters.js';
import {demoNotices,demoUnits,demoInitialSources} from './demoData.js';
export function createLiveRepository(request=createHttpClient()){
 return {
  async bootstrap(signal){const [sites,subs,messages]=await Promise.all([request('/sites',{signal}),request('/subscriptions',{signal}),request('/messages?mode=live',{signal})]);return {sites:sites.items.map(siteFromApi),subscriptions:subscriptionFromApi(subs),messages:messages.items.map(messageFromApi),unread:messages.unread}},
  async listNotices({q='',tab='all',page=0,size=6,source='',category=''}={},signal){const params=new URLSearchParams({mode:'live',q,limit:String(size),offset:String(page*size),read:tab==='saved'?'favorite':'all',subscribed:tab==='subscribed'?'1':'0',source:String(source),category});const data=await request(`/notices?${params}`,{signal});if(data.items.length>size)throw new Error('后端尚未支持分页，请重启更新后的通知后端');return {items:data.items.map(noticeFromApi),total:data.total}},
  async getNotice(id){return noticeFromApi(await request(`/notices/${id}`))},
  async updateNotice(id,changes){return noticeFromApi(await request(`/notices/${id}`,{method:'PATCH',body:changes}))},
  async saveSubscriptions(s){return subscriptionFromApi(await request('/subscriptions',{method:'PUT',body:subscriptionToApi(s)}))},
  async readMessage(id){await request(`/messages/${id}`,{method:'PATCH',body:{read:true}})},
 };
}
export function createDemoRepository(){
 const sites=demoUnits.map((name,i)=>({id:i+1,name,type:i===1||i===2?'二级学院':'职能与服务单位',url:null,status:'演示',enabled:false,error:''}));
 let subscriptions={sources:sites.filter(s=>demoInitialSources.includes(s.name)).map(s=>s.id),keywords:['人工智能','课程安排','国际交流'],categories:['教学教务','学术讲座','国际交流','校园服务'],inApp:true};
 let notices=demoNotices.map(n=>({...n,sourceId:sites.find(s=>s.name===n.source).id,isDemo:true,favorite:n.id===1,read:false,url:null,dateVerified:true,category:n.category==='研究生培养'?'教学教务':n.category}));
 let messages=notices.slice(0,3).map(n=>({id:n.id,noticeId:n.id,title:n.title,source:n.source,date:n.date,status:'演示',read:false,isDemo:true}));
 const copy=x=>structuredClone(x);
 return {
  async bootstrap(){return copy({sites,subscriptions,messages,unread:messages.filter(m=>!m.read).length})},
  async listNotices({q='',tab='all',page=0,size=6,source='',category=''}={}){const items=notices.filter(n=>(!q||[n.title,n.summary,n.source].join(' ').includes(q))&&(!source||n.sourceId===Number(source))&&(!category||n.category===category)&&(tab==='saved'?n.favorite:tab==='subscribed'?subscriptions.sources.includes(n.sourceId)||subscriptions.categories.includes(n.category)||subscriptions.keywords.some(k=>n.title.includes(k)):true));return copy({items:items.slice(page*size,(page+1)*size),total:items.length})},
  async getNotice(id){const n=notices.find(n=>n.id===id);if(!n)throw new Error('通知不存在');return copy(n)},
  async updateNotice(id,patch){const n=notices.find(n=>n.id===id);if(!n)throw new Error('通知不存在');Object.assign(n,patch);return copy(n)},
  async saveSubscriptions(s){subscriptions=copy(s);return copy(s)},
  async readMessage(id){const m=messages.find(m=>m.id===id);if(m)m.read=true},
 };
}
