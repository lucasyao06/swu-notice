# API contract (all endpoints under /api)
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
All errors JSON {error:string} with appropriate HTTP code. CORS allow local frontend origins 127.0.0.1:5173 and localhost:5173 only. No arbitrary outbound URL fetch: list URL must stay on registered website host, reject private addresses and unsafe redirects. Exception: fixed directory HTTPS hosts using a configured system HTTPS proxy may resolve into the recognized Fake-IP ranges 198.18.0.0/15 or fdfe:dcba:9876::/48; certificate validation remains enabled. Save validates URL structure/origin only; DNS is checked at fetch time. Crawl follows robots.txt and limited page/request budget, timeout. No authentication bypass. Source status describes page access health; backfill and dates awaiting verification are tracked separately in coverage. Matching live notices can create one persistent in-app message per notice, including when detail-page classification first matches a subscription.

2026-09-29 glass frontend compatibility additions:
- GET /notices optionally accepts `limit` (integer 1..100) and `offset` (integer >=0). `total` remains the full filtered count, `items` is the selected page. Without `limit`, previous unpaginated behavior remains.
- GET /notices/:id returns a single notice or 404; same record shape as the list.


2026-10-03 collector repairs:
- GET /sites includes `coverage: {checked,pending,failed,unverified,sections,updated_at}`. `failed` counts access failures/timeouts; `unverified` counts articles lacking reliable publication metadata. Backfill or unverified dates alone do not change source status to delayed.
- GET /sites/:id/coverage exposes the persistent pages and pending frontier, plus `round_pages`, `round_new`, `round_success`, `round_failed`, `round_unverified`, and parser `metadata_version`.
- Notice identity is source + normalized HTTP/HTTPS URL, preserving query values while normalizing their order and removing tracking parameters. Existing duplicates merge on startup while retaining the oldest notice ID, read/favorite flags, sections, and one message. Before migration, an existing database with live records is backed up beside the database as `<stem>.before-collector-v5<suffix>`.
- Legacy attachments stay stored with user state but are excluded from notice/message lists and metadata repair queues. New attachment links are excluded during discovery and rejected at insertion.
- Publication metadata uses page metadata, labelled header fields, or header time elements. Body/summary dates are excluded. A failed detail-date extraction retains the existing list date and leaves it unverified.
- Classification uses deterministic rules over title, section, then extracted summary, within the existing six categories. Summary uses meta description or article body text, capped at 240 characters. Unknown topics retain the campus-service fallback.
- Each new collection run refreshes entry and section pages. Successful historical pages remain visited; pagination and detail work resume from the saved frontier. Incremental scans revisit pagination while newly discovered notices continue onto later pages, then stop refreshing known archive pages when no new notices are found. New undated articles take priority over archive work. Failed-page retries rotate and use at most one quarter of a batch (minimum one when the batch permits it), allowing the remaining archive to advance.
- Progress snapshots are saved every 10 attempted pages or 5 seconds, and at batch exit/cancellation. Reprocessing since the last snapshot is idempotent.
- Parser version 5 queues existing article metadata for one repair pass, including previously verified records; it does not invent missing summaries or dates without fetching the original page.

Regression checks (run from `swu-notice-monitor`):
```sh
python3 -m unittest discover -s tests -v
```
