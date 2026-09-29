export const CATEGORIES=['教学教务','学术讲座','竞赛活动','招生就业','国际交流','校园服务'];
export function safeUrl(value){try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null}catch{return null}}
export function noticeFromApi(n){
 const verified=Boolean(n.is_demo||n.date_verified);
 return {id:n.id,title:n.title,summary:n.summary||'',sourceId:n.source_id,source:n.source_name,sourceType:n.source_type,
  date:verified&&n.published_at?n.published_at.replace('T',' ').slice(0,16):'发布时间待核验',dateVerified:verified,dateSource:n.date_source||'',
  category:n.category,url:safeUrl(n.url),isDemo:Boolean(n.is_demo),read:Boolean(n.read),favorite:Boolean(n.favorite),sections:n.sections||'',tone:'blue'};
}
export function siteFromApi(s){return {id:s.id,name:s.name,type:s.type,url:safeUrl(s.url),status:s.status||'未接入',enabled:Boolean(s.enabled),lastChecked:s.last_checked,error:s.error||''}}
export function subscriptionFromApi(s){return {sources:[...s.sources],keywords:[...s.keywords],categories:[...s.categories],inApp:Boolean(s.in_app)}}
export function subscriptionToApi(s){return {sources:[...new Set(s.sources)],keywords:[...new Set(s.keywords.map(x=>x.trim()).filter(Boolean))],categories:[...new Set(s.categories)],in_app:s.inApp}}
export function messageFromApi(m){return {id:m.id,title:m.title,source:m.source_name,date:m.created_at,read:Boolean(m.read),status:m.status,noticeId:m.notice_id,isDemo:Boolean(m.is_demo)}}
