"""Bounded official competition collection with persisted per-source frontiers."""
import ipaddress
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

from .collector import FAKE_IP_NETWORKS, network_proxies, retry_network, read_robots, canonical_url
from .extraction import Tree, anchor_title, dates, extract_notices, extract_article_metadata, normalized

AGENT = 'SWUCompetitionMonitor/1.0 (educational official competition notices)'
KINDS = ['报名','赛程','规则','赛题','成绩','获奖公示','变更','其他参赛公告']
HOST_LOCKS = {}
HOST_LOCK = threading.Lock()


def classify(title):
    if re.search(r'圆满落幕|成功举办|精彩回顾|风采|人物专访|赞助商招募|教练论坛|培训视频|新闻报道|精彩瞬间|采购|招聘|总结大会|参赛高校|赛事介绍|常见问题|联系我们|关于我们', title, re.I):
        return None
    for kind, pattern in [('变更',r'变更|延期|延迟|调整|更名|勘误|update|change|postpone|correction'),
                          ('获奖公示',r'获奖|授奖|颁奖名单|奖项|award|winner'),
                          ('成绩',r'成绩|赛果|晋级|入围|排名|结果公示|results?|finalist'),
                          ('报名',r'报名|参赛通知|举办.*通知|注册|registration|register|invitation'),
                          ('赛程',r'赛程|时间安排|日程|赛场安排|报到|schedule|timeline'),
                          ('规则',r'规则|规程|章程|规范|要求|指南|申诉|考试大纲|技术方案.*发布|rules?|instructions?|guidelines?'),
                          ('赛题',r'赛题|题目发布|命题|题目公布|problems?|problem sets?')]:
        if re.search(pattern,title,re.I):
            return kind
    if re.search(r'通知|公告|名单|截止|提交|赛事安排|竞赛安排|赛事工作|announcement|deadline|submission',title,re.I):
        return '其他参赛公告'
    return None


def relevant(title, config):
    keys = config.get('keywords', [])
    return (not keys or any(x.casefold() in title.casefold() for x in keys)) and not any(x.casefold() in title.casefold() for x in config.get('exclude',[]))


def public_date(value):
    if not value:
        return ''
    value = str(value)
    # Never infer a year from MM-DD or treat a crawl timestamp as publication.
    found = next(dates(value),'')
    if not found:
        try: found = parsedate_to_datetime(value).date().isoformat()
        except (ValueError,TypeError): pass
    if not found:
        for pattern in ('%B %d, %Y','%b %d, %Y','%d %B %Y'):
            try:
                found = datetime.strptime(value.strip(),pattern).date().isoformat(); break
            except ValueError:
                pass
    return found if found and found <= date.today().isoformat() else ''


def safe_link(base, href):
    if not isinstance(href,str) or not href.strip():
        return None
    url = urllib.parse.urljoin(base,href)
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:
        return None
    try:
        if parsed.port not in (None,80 if parsed.scheme=='http' else 443):
            return None
    except ValueError:
        return None
    return canonical_url(url)


def article_publication(content):
    published=public_date(extract_article_metadata(content).get('published_at'))
    if published:
        return published
    # COMAP and other English sites use semantic <time> in a publication
    # header. Do not pick unlabelled event dates from the article body.
    for node in Tree(content).root.walk():
        if node.tag=='time' and node.parent:
            context=normalized(node.parent.text())
            if len(context)<240 and re.search(r'written on|published(?: on)?|posted on|发布时间|发布日期|发布于',context,re.I):
                published=public_date(node.attrs.get('datetime') or node.text())
                if published:return published
    return ''


def json_items(payload, base, config=None):
    out = []
    fields = (config or {}).get('json_fields', {})
    def walk(value):
        if isinstance(value,list):
            for child in value: walk(child)
        elif isinstance(value,dict):
            title = next((value[k] for k in fields.get('title',('title','name','headline','newsTitle','articleTitle')) if isinstance(value.get(k),str)), '')
            href = next((value[k] for k in fields.get('url',('url','link','href','newsUrl','articleUrl')) if isinstance(value.get(k),str)), '')
            if not href and (config or {}).get('json_url_template') and isinstance(value.get('id'),int):
                href = config['json_url_template'].format(id=value['id'])
            published = next((value[k] for k in fields.get('date',('datePublished','publishTime','published_at','publishDate','date','createTime')) if value.get(k)), '')
            url = safe_link(base,href)
            if title and url:
                attachments=[]
                if isinstance(value.get('content'),str):
                    for node in Tree(value['content']).root.walk():
                        link=safe_link(base,node.attrs.get('href','')) if node.tag=='a' else None
                        if link and re.search(r'\.(pdf|docx?|xlsx?|zip)(?:\?|$)',link,re.I):
                            attachments.append({'title':anchor_title(node) or '官网附件','url':link})
                out.append({'title':title.strip(),'url':url,'published_at':public_date(published),'kind':classify(title),'attachments':attachments,'detail_complete':bool(value.get('content'))})
            for child in value.values():
                if isinstance(child,(dict,list)): walk(child)
    walk(payload)
    return out


def parse_listing(content, base, config):
    """HTML, JSON/JSON-LD and RSS; no assumptions about campus URL patterns."""
    items, links = [], []
    if content.lstrip().startswith(('{','[')):
        payload = json.loads(content)
        items = json_items(payload,base,config)
        pagination = config.get('json_pagination')
        if pagination:
            result = payload.get('result', payload)
            page, total = result.get('pageIndex',result.get('current_page',1)), result.get('totalPages',result.get('total_pages',1))
            if isinstance(page,int) and isinstance(total,int) and page<total:
                parsed = urllib.parse.urlsplit(base)
                query = dict(urllib.parse.parse_qsl(parsed.query))
                query[pagination] = str(page+1)
                links.append(urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(query))))
    elif content.lstrip().startswith(('<?xml','<rss','<feed')):
        root = ET.fromstring(content)
        for entry in root.iter():
            if entry.tag.rsplit('}',1)[-1] not in ('item','entry'): continue
            values = {n.tag.rsplit('}',1)[-1]:(n.text or n.attrib.get('href','')) for n in entry}
            title = values.get('title','')
            href = safe_link(base,values.get('link',''))
            if href:
                items.append({'title':title,'url':href,'published_at':public_date(values.get('pubDate') or values.get('published')),'kind':classify(title),'attachments':[]})
    else:
        tree = Tree(content).root
        dated = {canonical_url(url):published for _,published,url in extract_notices(content,base)}
        for node in tree.walk():
            if node.tag == 'script' and node.attrs.get('type') in ('application/ld+json','application/json'):
                raw = ' '.join(x for x in node.children if isinstance(x,str))
                try: items.extend(json_items(json.loads(raw),base))
                except (ValueError,TypeError): pass
            if node.tag != 'a': continue
            title = anchor_title(node)
            href = safe_link(base,node.attrs.get('href',''))
            if not href: continue
            if re.fullmatch(r'下一页|下页|Next(?: page)?|[>»›]+|\d+|更多[>»›]*|more[>»›]*|公告|通知|赛事动态|通知公告|赛事公告|下载中心',title.strip(),re.I):
                links.append(href)
            kind = classify(title)
            if len(title)<8 or not kind or not relevant(title,config): continue
            published = dated.get(href,'')
            if not published:
                current = node.parent
                for _ in range(3):
                    if current is None: break
                    anchors = [x for x in current.walk() if x.tag=='a' and len(anchor_title(x))>=8]
                    if len(anchors)>1: break
                    # Exclude the title itself and descriptive body text.
                    text = normalized(current.text(lambda x:x.tag=='a' or x.tag in ('script','style')))
                    if len(text)<150:
                        published = public_date(text)
                    if published: break
                    current = current.parent
            items.append({'title':title,'url':href,'published_at':public_date(published),'kind':kind,'attachments':[]})
    seen = set()
    accepted = []
    for item in items:
        if item['kind'] and len(item['title'])>=8 and relevant(item['title'],config) and item['url'] not in seen:
            seen.add(item['url']); accepted.append(item)
    return accepted, list(dict.fromkeys(links))


def check_url(url, config, proxies, resolve=True):
    parsed = urllib.parse.urlsplit(url)
    base = urllib.parse.urlsplit(config['url'])
    hosts = set(config.get('allowed_hosts',[])) | {base.hostname}
    if parsed.hostname not in hosts or not safe_link(url,url):
        raise ValueError('目标不在已核验赛事主机范围内')
    if base.scheme=='https' and parsed.scheme!='https':
        raise ValueError('赛事HTTPS来源不能降级访问')
    if resolve:
        proxy_fake = parsed.scheme=='https' and bool(proxies.get('https')) and not urllib.request.proxy_bypass(parsed.netloc)
        for info in retry_network(lambda:socket.getaddrinfo(parsed.hostname,None)):
            addr = ipaddress.ip_address(info[4][0])
            if not addr.is_global and not (proxy_fake and any(addr.version==n.version and addr in n for n in FAKE_IP_NETWORKS)):
                raise ValueError('赛事目标解析到内网或保留地址')
    return url


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, config, proxies, before_redirect=None):
        self.config,self.proxies,self.before_redirect = config,proxies,before_redirect
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl,self.config,self.proxies)
        if self.before_redirect and not urllib.parse.urlsplit(req.full_url).path.endswith('/robots.txt'):
            self.before_redirect(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class OfficialFetcher:
    def __init__(self, config, cancel):
        self.config,self.cancel = config,cancel
        self.proxies = network_proxies()
        self.robots = {}
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler(self.proxies),OfficialRedirect(config,self.proxies,self._check_robots))
    def _check_robots(self,url):
        parsed=urllib.parse.urlsplit(url)
        origin=f'{parsed.scheme}://{parsed.netloc}'
        if origin not in self.robots:
            self.robots[origin]=read_robots(self.opener,origin+'/robots.txt')
        if not self.robots[origin].can_fetch(AGENT,url):
            raise ValueError('robots.txt 不允许采集此页面')
    def __call__(self,url):
        check_url(url,self.config,self.proxies)
        parsed = urllib.parse.urlsplit(url)
        origin = f'{parsed.scheme}://{parsed.netloc}'
        with HOST_LOCK:
            lock = HOST_LOCKS.setdefault(parsed.hostname,threading.Lock())
        with lock:
            if self.cancel.is_set(): raise InterruptedError('采集已停止')
            if origin not in self.robots:
                self.robots[origin] = read_robots(self.opener,origin+'/robots.txt')
            robots = self.robots[origin]
            if not robots.can_fetch(AGENT,url): raise ValueError('robots.txt 不允许采集此页面')
            if self.cancel.wait(max(.3,float(robots.crawl_delay(AGENT) or 0))): raise InterruptedError('采集已停止')
            def fetch():
                request = urllib.request.Request(url,headers={'User-Agent':AGENT,'Accept':'text/html,application/json,application/xml'})
                with self.opener.open(request,timeout=15) as response:
                    # Redirect destination has its own robots policy.
                    final = response.url
                    check_url(final,self.config,self.proxies)
                    final_parts = urllib.parse.urlsplit(final)
                    final_origin = f'{final_parts.scheme}://{final_parts.netloc}'
                    if final_origin not in self.robots:
                        self.robots[final_origin] = read_robots(self.opener,final_origin+'/robots.txt')
                    if not self.robots[final_origin].can_fetch(AGENT,final): raise ValueError('robots.txt 不允许最终目标页面')
                    raw = response.read(1_500_001)
                    if len(raw)>1_500_000: raise ValueError('赛事页面超过大小限制')
                    charset = response.headers.get_content_charset()
                    if not charset:
                        match = re.search(br'charset\s*=\s*["\x27]?([\w-]+)',raw[:4000],re.I)
                        charset = match[1].decode('ascii') if match else 'utf-8'
                    return raw.decode(charset,errors='replace'),final
            return retry_network(fetch)


def collect_source(store, source, fetch=None, budget=None):
    config = source['config']
    fetch = fetch or OfficialFetcher(config,store.cancel)
    old = source['checkpoint']
    entry = config.get('list_url') or config['url']
    queue = list(old.get('pending',[])) or [{'url':entry,'kind':'list'}]
    visited = set(old.get('visited',[])) if old.get('pending') else set()
    for queued in queue:
        if queued.get('error'): visited.discard(queued['url'])
    if source['baseline'] and old.get('pending'):
        queue = [{'url':entry,'kind':'list'}]+[p for p in queue if p['url']!=entry]
        visited.discard(entry)
    errors = []; found = int(old.get('found',0)) if old.get('pending') else 0
    processed = 0; inserted = 0
    max_pages = budget or config.get('max_pages',24)
    started = time.monotonic()
    def checkpoint(status,complete=False):
        store.checkpoint(source['id'],{'pending':queue+errors,'visited':sorted(visited),'found':found},status,
            '；'.join(e.get('error','') for e in errors[:3]),complete)
    while queue and processed<max_pages and time.monotonic()-started<90 and not store.cancel.is_set():
        page = queue.pop(0)
        if page['url'] in visited: continue
        processed += 1
        try:
            check_url(page['url'],config,{},resolve=False)
            content,effective = fetch(page['url'])
            if page['kind']=='detail':
                item = dict(page['item'])
                item['published_at'] = article_publication(content) or item['published_at']
                attachments = []
                for node in Tree(content).root.walk():
                    if node.tag!='a': continue
                    href = safe_link(effective,node.attrs.get('href',''))
                    if href and re.search(r'\.(pdf|docx?|xlsx?|zip)(?:\?|$)',href,re.I):
                        attachments.append({'title':anchor_title(node) or '官网附件','url':href})
                item['attachments'] = attachments
                _,created=store.upsert_notice(source,item)
                inserted+=int(created)
            else:
                items,links = parse_listing(content,effective,config)
                accepted = 0
                for item in items:
                    try: check_url(item['url'],config,{},resolve=False)
                    except ValueError: continue
                    accepted += 1
                    if item['published_at'] and item['published_at']<(date.today()-timedelta(days=365)).isoformat(): continue
                    attachment=bool(re.search(r'\.(pdf|docx?|xlsx?|zip)(?:\?|$)',item['url'],re.I))
                    needs_detail=config.get('detail_fetch',True) and not item.get('detail_complete') and not attachment
                    if attachment:item['attachments']=[{'title':item['title'],'url':item['url']}]
                    # Resolve an undated detail before alerting: it may prove
                    # to be an old announcement outside the backfill window.
                    if item['published_at'] or not needs_detail:
                        _,created = store.upsert_notice(source,item)
                        inserted += int(created)
                    if needs_detail:
                        if item['url'] not in visited and not any(p['url']==item['url'] for p in queue):
                            queue.append({'url':item['url'],'kind':'detail','item':item})
                found += accepted
                # If an entire chronological page predates the backfill window,
                # do not traverse its older archive pages.
                old_page = bool(items) and all(x['published_at'] and x['published_at']<(date.today()-timedelta(days=365)).isoformat() for x in items)
                for link in ([] if old_page else links):
                    try: check_url(link,config,{},resolve=False)
                    except ValueError: continue
                    # Explicit source scope; do not scan the whole organizer site.
                    if link in visited or any(p['url']==link for p in queue): continue
                    if config.get('path_prefix') and not urllib.parse.urlsplit(link).path.startswith(config['path_prefix']): continue
                    if len(visited)+len(queue)<1000: queue.append({'url':link,'kind':'list'})
            visited.add(page['url'])
        except InterruptedError:
            queue.insert(0,page); break
        except (OSError,ValueError,LookupError,ET.ParseError) as exc:
            errors.append({**page,'error':str(exc)[:400]})
        checkpoint('采集中')
    status = '失败' if errors else '待继续' if queue else '正常' if found else '解析受限'
    if not found and not queue and not errors:
        errors.append({'url':entry,'kind':'list','error':'未识别到参赛公告；可能需要公开接口或专用解析器，不能认定官网没有通知。'})
    checkpoint(status,complete=not queue and not errors and found>0)
    return {'source':source['id'],'processed':processed,'inserted':inserted,'pending':len(queue)+len(errors),'status':status}


def run_collection(store, competition_id=None, college_id=None):
    sources = store.sources(competition_id,college_id)
    results = []
    try:
        def collect_batches(source):
            processed = inserted = 0
            while not store.cancel.is_set():
                result = collect_source(store,source)
                processed += result['processed']; inserted += result['inserted']
                if result['status']!='待继续' or not result['processed'] or processed>=1000: break
                source = next(s for s in store.sources(source['competition_id']) if s['id']==source['id'])
            return {**(result if processed else {'source':source['id'],'status':'已停止'}),'processed':processed,'inserted':inserted}
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='competition') as pool:
            futures = {pool.submit(collect_batches,source):source for source in sources}
            for future in as_completed(futures):
                source = futures[future]
                try: result = future.result()
                except Exception as exc:
                    store.checkpoint(source['id'],source['checkpoint'],'失败',str(exc)[:400]); result={'source':source['id'],'status':'失败'}
                results.append(result)
                store.progress({'competition_id':competition_id,'college_id':college_id,'completed':len(results),'total':len(sources),
                                'stopping':store.cancel.is_set(),'results':results})
    finally:
        store.progress({'competition_id':competition_id,'college_id':college_id,'completed':len(results),'total':len(sources),
                        'stopping':store.cancel.is_set(),'results':results},finished=True)


def start_collection(store, competition_id=None, college_id=None):
    if college_id is not None:
        store.college(college_id)
        if competition_id and not store.reference(competition_id,college_id)['reference_rules']:
            raise ValueError('所选赛事未在当前学院截图列名，请按单赛事或全平台采集')
    if competition_id is not None and competition_id not in {x['id'] for x in store.catalog['items']}:
        raise ValueError('赛事不存在')
    if competition_id and not store.sources(competition_id):
        raise ValueError('此赛事尚未核验公开采集入口')
    if college_id and not store.sources(college_id=college_id):
        raise ValueError('此学院赛事尚未核验公开采集入口')
    if not store.claim(competition_id,college_id): return False
    store.thread = threading.Thread(target=run_collection,args=(store,competition_id,college_id),daemon=True)
    try: store.thread.start()
    except Exception:
        store.progress({'competition_id':competition_id},finished=True); raise
    return True


def scheduler_loop(store, stop):
    next_run = time.monotonic()
    state=store.crawl_state()
    if state.get('last_finished'):
        elapsed=(datetime.now().astimezone()-datetime.fromisoformat(state['last_finished'])).total_seconds()
        next_run+=max(0,store.settings()['interval_minutes']*60-elapsed)
    if store.resume_requested:
        start_collection(store,store.resume_id,getattr(store,'resume_college_id',None))
    while not stop.wait(5):
        settings = store.settings()
        if settings['scheduler_enabled'] and time.monotonic()>=next_run:
            # A manual/resumed run also consumes this interval; stopping it
            # must not cause the scheduler to immediately launch it again.
            if store.crawl_state()['running'] or start_collection(store):
                next_run=time.monotonic()+settings['interval_minutes']*60
        elif not settings['scheduler_enabled']: next_run=time.monotonic()
