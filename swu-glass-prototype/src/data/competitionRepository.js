import catalog from '../../../swu-notice-monitor/data/competitions.json' with {type:'json'};
import {createHttpClient} from './httpClient.js';
export const COMPETITION_KINDS=['报名','赛程','规则','赛题','成绩','获奖公示','变更','其他参赛公告'];
export function createCompetitionRepository(request=createHttpClient()){
 const call=(path,options)=>request(`/competition/${path}`,options);
 return {
  catalog:signal=>call('catalog',{signal}),
  notices:({q='',competition='',kind='',tab='all',page=0}={},signal)=>call(`notices?${new URLSearchParams({q,competition,kind,tab,limit:'10',offset:String(page*10)})}`,{signal}),
  notice:id=>call(`notices/${id}`),
  update:(id,body)=>call(`notices/${id}`,{method:'PATCH',body}),
  subscriptions:signal=>call('subscriptions',{signal}),
  follow:competitions=>call('subscriptions',{method:'PUT',body:{competitions}}),
  messages:(page=0,signal)=>call(`messages?limit=10&offset=${page*10}`,{signal}),
  readMessage:id=>call(id==null?'messages':`messages/${id}`,{method:'PATCH',body:{read:true}}),
  crawl:signal=>call('crawl',{signal}),
  start:competition_id=>call('crawl',{method:'POST',body:competition_id?{competition_id}:{}}),
  stop:()=>call('crawl/stop',{method:'POST',body:{}}),
  settings:signal=>call('settings',{signal}),
  saveSettings:body=>call('settings',{method:'PUT',body}),
 };
}
export function createCompetitionDemoRepository(){
 const copy=x=>structuredClone(x);
 let following=['cumcm','ccpc'];
 const notices=[
  {id:1,competition_id:'cumcm',competition_name:'全国大学生数学建模竞赛（高教社杯）',title:'示例：数学建模竞赛报名通知',kind:'报名',published_at:'2026-09-22',date_verified:true},
  {id:2,competition_id:'ccpc',competition_name:'中国大学生程序设计竞赛（CCPC）',title:'示例：CCPC比赛赛程安排',kind:'赛程',published_at:'2026-09-21',date_verified:true},
  {id:3,competition_id:'robotac',competition_name:'全国大学生机器人大赛-RoboTac',title:'示例：ROBOTAC获奖名单公示',kind:'获奖公示',published_at:'',date_verified:false},
 ].map(n=>({...n,url:null,attachments:[],read:false,favorite:false,collected_at:'2026-09-22',is_demo:true}));
 const messages=notices.slice(0,2).map(n=>({id:n.id,notice_id:n.id,title:n.title,competition_id:n.competition_id,competition_name:n.competition_name,created_at:n.collected_at,read:false}));
 let settings={interval_minutes:300,scheduler_enabled:false};
 return {
  async catalog(){return copy({policy:catalog.policy,kinds:COMPETITION_KINDS,items:catalog.items.map(x=>({...x,official_url:null,status:'演示',error:'',last_checked:null,notice_count:notices.filter(n=>n.competition_id===x.id).length,followed:following.includes(x.id),sources:[],awards:x.awards||catalog.policy.awards,scores:x.scores||catalog.policy.score_groups[x.score_group]}))})},
  async notices({q='',competition='',kind='',tab='all',page=0}={}){const rows=notices.filter(n=>(!q||[n.title,n.competition_name].join(' ').includes(q))&&(!competition||n.competition_id===competition)&&(!kind||n.kind===kind)&&(tab==='following'?following.includes(n.competition_id):tab==='favorite'?n.favorite:tab==='unread'?!n.read:true));return copy({items:rows.slice(page*10,page*10+10),total:rows.length})},
  async notice(id){const n=notices.find(n=>n.id===id);if(!n)throw new Error('赛事通知不存在');return copy(n)},
  async update(id,body){const n=notices.find(n=>n.id===id);if(!n)throw new Error('赛事通知不存在');Object.assign(n,body);if(body.read)messages.filter(m=>m.notice_id===id).forEach(m=>{m.read=true});return copy(n)},
  async subscriptions(){return copy({competitions:following})},
  async follow(ids){following=copy(ids);return copy({competitions:following})},
  async messages(page=0){return copy({items:messages.slice(page*10,page*10+10),total:messages.length,unread:messages.filter(m=>!m.read).length})},
  async readMessage(id){messages.filter(m=>id==null||m.id===id).forEach(m=>{m.read=true});return {ok:true}},
  async crawl(){return {running:false,last_finished:null}},
  async start(){throw new Error('演示模式不访问真实官网，请切换真实数据后采集')},
  async stop(){return {ok:true}},
  async settings(){return copy(settings)},
  async saveSettings(value){settings=copy(value);return copy(settings)},
 };
}
