# API contract (all endpoints under /api)
Competition endpoints use the separate `/api/competition/` namespace. See [competition module contract](competition-module.md#接口); they do not accept campus `mode` or affect campus subscriptions/messages/settings. Competition demo state is frontend-only.
Default port 8765. JSON. Single local user. All notice datasets selected by `mode=demo|live` (default demo).

- GET /health -> {ok:true}
- GET /sites -> {items:[{id,name,url,type,group,note,status,last_checked,new_count,enabled,list_url,error}],total:89}
- PATCH /sites {enabled:boolean} -> {items:[all sites],total:89,enabled_count:integer}; preserves list URLs and recorded status.
- PATCH /sites/:id {enabled:boolean,list_url:string} -> updated site
- GET /notices?mode=demo&q=&type=&category=&read=all|unread|read|favorite&source=&period=all|today|week|month|custom&start=&end=&subscribed=0 -> {items:[{id,title,source_id,source_name,source_type,published_at,category,summary,url,is_demo,read,favorite}],total}
- PATCH /notices/:id {read?:boolean,favorite?:boolean} -> updated notice
- GET /subscriptions -> {sources:[integer],keywords:[string],categories:[string],in_app:boolean}
- PUT /subscriptions with same full shape -> saved shape
- GET /messages?mode=demo -> {items:[{id,title,source_name,created_at,status,read,notice_id,is_demo}],unread:integer}
- PATCH /messages/:id {read:true} -> {ok:true}
- GET /stats?mode=demo -> {directory_count,connected_count,today_count,error_count,subscriber_count,push_rate,trend:[{date,count}],activity:[{name,count}],categories:[{name,count}],last_updated,mode}
- GET /settings -> {interval_minutes:60,scheduler_enabled:false}
- PUT /settings same shape -> saved settings
- POST /crawl {site_id?:integer} -> {ok:true,running:true}; async collector; no argument only enabled sources.
- GET /crawl -> {running:boolean,last_finished:string|null,...optional progress}

Demo is explicitly seeded with September 2026 dates. Demo reference today is 2026-09-22. Live today uses current local date. Five demo notices match brief; optional additional historical demo items for charts. Use real imported source IDs. No real stats invented. Demo notifications labelled is_demo.
All errors JSON {error:string} with appropriate HTTP code. CORS allow local frontend origins 127.0.0.1:5173 and localhost:5173 only. No arbitrary outbound URL fetch: list URL must stay on registered website host, reject private addresses and unsafe redirects. Exception: fixed directory HTTPS hosts using a configured system HTTPS proxy may resolve into the recognized Fake-IP ranges 198.18.0.0/15 or fdfe:dcba:9876::/48; certificate validation remains enabled. Save validates URL structure/origin only; DNS is checked at fetch time. Crawl follows robots.txt and limited page/request budget, timeout. No authentication bypass. A successful fetch without extracted dated notifications is not 'normal'; report parser limitation. Only live inserted notifications can trigger actual persistent in-app messages.

2026-09-29 glass frontend compatibility additions:
- GET /notices optionally accepts `limit` (integer 1..100) and `offset` (integer >=0). `total` remains the full filtered count, `items` is the selected page. Without `limit`, previous unpaginated behavior remains.
- GET /notices/:id returns a single notice or 404; same record shape as the list.
