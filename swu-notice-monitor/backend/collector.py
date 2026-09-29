import ipaddress
import os
import ssl
import random
import json
from pathlib import Path
import re
import socket
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import datetime
from html.parser import HTMLParser


DATE_RE = re.compile(r"(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})日?")


class LinkParser(HTMLParser):
    """Keep the title separate from card body/date text inside a shared link."""
    VOID_TAGS = {'img', 'br', 'hr', 'input', 'meta', 'link', 'source', 'wbr'}
    BLOCK_TAGS = {'div', 'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'section'}

    def __init__(self):
        super().__init__()
        self.links = []
        self.records = []
        self._anchor_data = None
        self._stack = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)
        if tag == 'a':
            self._anchor_data = {'href': attrs.get('href', ''),
                                 'attribute': attrs.get('title', ''),
                                 'full': [], 'plain': [], 'heading': []}
            self._stack = []
        elif self._anchor_data is not None:
            cls = attrs.get('class', '').lower()
            excluded = tag in {'script', 'style', 'time'} or bool(re.search(
                r'(?:^|[\s_-])(?:desc|description|summary|intro|brief|date|time|year|month)(?:$|[\s_-])', cls))
            heading = tag in {'h1','h2','h3','h4','h5','h6'} or bool(re.search(
                r'(?:^|[\s_-])(?:title|tit|headline|bt)(?:$|[\s_-])', cls))
            if tag in self.BLOCK_TAGS:
                self._anchor_data['plain'].append('\n')
            if tag not in self.VOID_TAGS:
                self._stack.append((tag, excluded, heading))

    def handle_data(self, data):
        if self._anchor_data is None:
            return
        self._anchor_data['full'].append(data)
        if not any(item[1] for item in self._stack):
            self._anchor_data['plain'].append(data)
            if any(item[2] for item in self._stack):
                self._anchor_data['heading'].append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self._anchor_data is None:
            return
        if tag == 'a':
            a = self._anchor_data
            heading = ''.join(a['heading']).strip()
            # Structural blocks separate a card title from its body. Plain inline
            # text (including English words) remains intact; never split on spaces.
            plain = next((line.strip() for line in ''.join(a['plain']).splitlines() if line.strip()), '')
            title = ' '.join((a['attribute'].strip() or heading or plain).split())
            full = ' '.join(' '.join(a['full']).split())
            self.links.append((a['href'], title))
            self.records.append({'href': a['href'], 'title': title, 'text': full})
            self._anchor_data = None
            self._stack = []
        else:
            for i in range(len(self._stack)-1, -1, -1):
                if self._stack[i][0] == tag:
                    del self._stack[i:]
                    break
            if tag in self.BLOCK_TAGS:
                self._anchor_data['plain'].append('\n')


class DatedContainerParser(LinkParser):
    def __init__(self):
        super().__init__()
        self._containers = []
        self.containers = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('li', 'tr'):
            self._containers.append({'tag': tag.lower(), 'text': [], 'anchors': []})
        super().handle_starttag(tag, attrs)

    def handle_data(self, data):
        for container in self._containers:
            container['text'].append(data)
        super().handle_data(data)

    def handle_endtag(self, tag):
        before = len(self.records)
        super().handle_endtag(tag)
        if len(self.records) > before and self._containers:
            r = self.records[-1]
            self._containers[-1]['anchors'].append((r['href'], r['title']))
        if tag.lower() in ('li', 'tr'):
            for index in range(len(self._containers)-1, -1, -1):
                if self._containers[index]['tag'] == tag.lower():
                    self.containers.append(self._containers.pop(index))
                    break


def _valid_date(match):
    try:
        value = datetime(*map(int, match.groups())).date()
    except ValueError:
        return None
    return value.isoformat()


def _candidate_score(base_url, href, title):
    base_host = urllib.parse.urlparse(base_url).hostname
    if len(title) < 6 or title in {"首页", "更多", "查看详情", "上一页", "下一页"}:
        return -1, None
    url = urllib.parse.urljoin(base_url, href)
    parsed = urllib.parse.urlparse(url)
    if parsed.hostname != base_host or parsed.scheme not in ("http", "https"):
        return -1, None
    path = parsed.path.lower()
    if not path or path == "/" or href.startswith(("#", "javascript:")):
        return -1, None
    preferred = bool(re.search(r"/(?:info|content)(?:/|[_-])", path) or path.endswith((".htm", ".html")))
    return (2 if preferred else 1), url


# Shared structural parser used by both lists and detail-page verification.
try:
    from .extraction import extract_notices, extract_article_metadata, discover_articles
except ImportError:
    from extraction import extract_notices, extract_article_metadata, discover_articles


# Only the fixed, user-provided directory can use the system proxy's Fake-IP DNS.
# HTTPS still verifies the registered hostname certificate; ordinary LAN addresses
# remain forbidden. No arbitrary hostname or port can opt into this exception.
DIRECTORY_HOSTS = frozenset(urllib.parse.urlparse(row["url"]).hostname for row in
    json.loads((Path(__file__).resolve().parents[1] / "data" / "sites.json").read_text()))
FAKE_IP_NETWORKS = (ipaddress.ip_network("198.18.0.0/15"),
                    ipaddress.ip_network("fdfe:dcba:9876::/48"),
                    ipaddress.ip_network("2001:2::/48"))


def network_proxies():
    mode = os.environ.get('SWU_NETWORK_MODE', 'auto').lower()
    if mode == 'direct': return {}
    if mode == 'auto': return urllib.request.getproxies()
    if mode != 'proxy': raise ValueError('[NETWORK_CONFIG] SWU_NETWORK_MODE 必须是 auto、direct 或 proxy')
    url = os.environ.get('SWU_HTTPS_PROXY', '').strip()
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in ('http','https') or not parsed.hostname:
        raise ValueError('[NETWORK_CONFIG] proxy 模式需要有效的 SWU_HTTPS_PROXY（HTTP/HTTPS 代理）')
    return {'http': url, 'https': url}


def network_summary():
    proxies = network_proxies()
    return {'mode': os.environ.get('SWU_NETWORK_MODE','auto'),
            'proxy_configured': bool(proxies.get('https')),
            'proxy_host': urllib.parse.urlsplit(proxies.get('https','')).hostname,
            'proxy_port': urllib.parse.urlsplit(proxies.get('https','')).port,
            'timeout_seconds': 15, 'max_attempts': 3}


def retry_network(call):
    """Retry read-only transient failures, never TLS/policy/403/404 failures."""
    for attempt in range(3):
        try: return call()
        except (OSError, urllib.error.URLError) as exc:
            reason = getattr(exc, 'reason', exc)
            if isinstance(reason, ssl.SSLCertVerificationError): raise
            if isinstance(reason, ssl.SSLError) and not isinstance(reason, (ssl.SSLEOFError, ssl.SSLZeroReturnError)): raise
            status = getattr(exc, 'code', None)
            retryable = status in (408,429,500,502,503,504) if status else isinstance(reason, (TimeoutError, socket.gaierror, ConnectionError, OSError))
            if not retryable or attempt == 2: raise
            delay = .5 * (2**attempt) + random.uniform(0,.2)
            if status == 429:
                hint = exc.headers.get('Retry-After','') if exc.headers else ''
                if hint.isdigit(): delay = min(30, max(delay,int(hint)))
            if isinstance(exc, urllib.error.HTTPError): exc.close()
            time.sleep(delay)


def _resolved_public(host, proxy_compatible=False):
    try:
        addresses = retry_network(lambda: socket.getaddrinfo(host, None))
    except socket.gaierror as exc:
        raise ValueError("[DNS_UNAVAILABLE] 域名解析失败，已重试3次；检查服务器DNS或代理配置") from exc
    for item in addresses:
        address = ipaddress.ip_address(item[4][0])
        if not address.is_global:
            is_fake = any(address.version == network.version and address in network
                          for network in FAKE_IP_NETWORKS)
            if not (proxy_compatible and is_fake):
                if is_fake:
                    raise ValueError('[PROXY_REQUIRED] DNS返回代理虚拟地址，但未使用有效代理；配置 SWU_NETWORK_MODE=proxy 和 SWU_HTTPS_PROXY，或改用公网DNS直连')
                raise ValueError('[PRIVATE_ADDRESS] 目标解析到内网或保留地址，已阻止访问；请检查服务器DNS')


def validate_list_url(site_url, list_url):
    base, target = urllib.parse.urlparse(site_url), urllib.parse.urlparse(list_url)
    if target.scheme not in ("http", "https") or not target.hostname:
        raise ValueError("列表地址必须是 http(s) URL")
    if (base.hostname or "").lower() != target.hostname.lower():
        raise ValueError("列表地址必须与登记网站同一主机")
    if target.username is not None or target.password is not None:
        raise ValueError("列表地址不能包含用户名或密码")
    if target.port not in (None, 443 if target.scheme == "https" else 80):
        raise ValueError("列表地址只支持标准 HTTP/HTTPS 端口")
    if base.scheme == "https" and target.scheme != "https":
        raise ValueError("已登记 HTTPS 网站不能降级为 HTTP")
    return list_url


def collection_target(site_url, url):
    base, target = urllib.parse.urlsplit(site_url), urllib.parse.urlsplit(url)
    if (base.scheme == 'https' and target.scheme == 'http' and base.hostname == target.hostname
            and target.port in (None, 80) and target.username is None and target.password is None):
        url = urllib.parse.urlunsplit(('https', base.netloc, target.path, target.query, target.fragment))
    validate_list_url(site_url, url)
    return url


def validate_fetch_url(url, proxies=None):
    parsed = urllib.parse.urlparse(url)
    validate_list_url(url, url)
    proxies = network_proxies() if proxies is None else proxies
    proxy_compatible = (parsed.scheme == "https" and parsed.hostname in DIRECTORY_HOSTS
                        and bool(proxies.get("https"))
                        and not urllib.request.proxy_bypass(parsed.netloc))
    _resolved_public(parsed.hostname, proxy_compatible=proxy_compatible)
    return url


def crawl_failure_status(exc):
    reason = getattr(exc, "reason", None)
    if isinstance(exc, TimeoutError) or isinstance(reason, TimeoutError) or "timed out" in str(exc).lower():
        return "延迟"
    return "失败"


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, allowed_host, proxies=None):
        self.allowed_host = allowed_host
        self.proxies = proxies

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urllib.parse.urlparse(newurl)
        if parsed.hostname != self.allowed_host or parsed.scheme not in ("http", "https"):
            raise urllib.error.HTTPError(newurl, code, "unsafe redirect", headers, fp)
        validate_list_url(req.full_url, newurl)
        validate_fetch_url(newurl, self.proxies)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _read_robots_once(opener, robots_url, max_bytes=128_000):
    request = urllib.request.Request(robots_url, headers={"User-Agent": "SWUNoticeMonitor/1.0"})
    try:
        with opener.open(request, timeout=15) as response:
            raw = response.read(max_bytes + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        exc.close()
        if status == 404:
            raw = b"User-agent: *\nDisallow:\n"
        elif status in (401, 403):
            raw = b"User-agent: *\nDisallow: /\n"
        else:
            raise
    if len(raw) > max_bytes:
        raise ValueError("robots.txt 超过安全大小限制")
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(raw.decode("utf-8", errors="replace").splitlines())
    return parser


def read_robots(opener, robots_url, max_bytes=128_000):
    return retry_network(lambda: _read_robots_once(opener, robots_url, max_bytes))


def canonical_url(url):
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.urlencode(sorted((k,v) for k,v in urllib.parse.parse_qsl(parsed.query)
        if not k.lower().startswith('utm_')))
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.lower(), parsed.path or '/', query, ''))


def discover_sections(html, base_url, parent_label='网站首页'):
    """Discover public navigation and pagination, excluding dated article links."""
    parser = LinkParser()
    parser.feed(html)
    articles = {canonical_url(n[2]) for n in extract_notices(html, base_url)}
    articles.update(canonical_url(n['url']) for n in discover_articles(html, base_url))
    found, seen = [], set()
    for href, label in parser.links:
        label = ' '.join(label.split())
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        url = canonical_url(urllib.parse.urljoin(base_url, href))
        target = urllib.parse.urlsplit(url)
        if url in seen or url in articles or url == canonical_url(base_url):
            continue
        if re.search(r'/(?:info|content|__local|system)(?:/|[_-])', target.path, re.I):
            continue
        if re.search(r'\.(?:pdf|docx?|xlsx?|pptx?|zip|rar|jpg|png|gif|mp4|mp3|css|js)$', target.path, re.I):
            continue
        if re.search(r'login|logout|delete|remove|signout|download', target.path, re.I):
            continue
        if not label or len(label) > 40 or re.search(r'登录|退出|检索|搜索', label):
            continue
        try:
            validate_list_url(base_url, url)
        except ValueError:
            continue
        pagination = bool(re.fullmatch(r'\d+|[<>«»‹›]+|(?:上|下)(?:一)?页|首页|尾页|末页|第一页|最后一页|Next|Previous', label, re.I))
        # Bare numeric links only make sense on pages containing dated entries.
        if label.isdigit() and not articles:
            continue
        seen.add(url)
        found.append({'url': url, 'label': parent_label if pagination or label in {'更多','更多>>','查看更多'} else label})
    return found


def discover_notice_lists(html, base_url):
    # Kept for callers of the original discovery helper; no keyword or 3-link cap.
    return [item['url'] for item in discover_sections(html, base_url)]


def _fetch_html_once(opener, url, agent, max_bytes):
    validate_fetch_url(url, getattr(opener, "swu_proxies", None))
    request = urllib.request.Request(url, headers={"User-Agent": agent, "Accept": "text/html"})
    with opener.open(request, timeout=15) as response:
        content_type = response.headers.get_content_type()
        if content_type not in ("text/html", "application/xhtml+xml"):
            raise ValueError("列表地址未返回 HTML")
        raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ValueError("页面超过安全大小限制")
        charset = response.headers.get_content_charset()
        if not charset:
            match = re.search(br'charset=["\']?([a-zA-Z0-9_-]+)', raw[:4096], re.I)
            charset = match.group(1).decode("ascii") if match else "utf-8"
        return raw.decode(charset, errors="replace"), response.geturl()


def fetch_html(opener, url, agent, max_bytes):
    return retry_network(lambda: _fetch_html_once(opener, url, agent, max_bytes))


def collect_site(store, site, max_bytes=750_000, max_pages=80, max_seconds=120):
    root = canonical_url(site['url'])
    proxies = network_proxies()
    validate_fetch_url(root, proxies)
    parsed = urllib.parse.urlparse(root)
    robots_url = urllib.parse.urlunparse((parsed.scheme, parsed.netloc, '/robots.txt', '', '', ''))
    agent = 'SWUNoticeMonitor/1.0 (local educational notice aggregator)'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler(proxies), SafeRedirect(parsed.hostname, proxies))
    opener.swu_proxies = proxies
    robots = read_robots(opener, robots_url)
    old = store.get_coverage(site['id'])
    # Persist the frontier: large archives continue on the next manual/scheduled run.
    parser_updated = old.get('metadata_version') != 4
    pages = {p['url']: p for p in old['pages']} if (old['pending'] or parser_updated) and old.get('version') == 2 else {}
    queue = deque(old['pending'])
    seeds = [{'url': root, 'label': '网站首页'}]
    if site['list_url']:
        validate_list_url(root, site['list_url'])
        seeds.append({'url': canonical_url(site['list_url']), 'label': '自定义入口'})
    # Refresh entry pages each round so archive backfill does not hide new posts.
    seed_urls = {p['url'] for p in seeds}
    queue = deque(seeds + [p for p in queue if p['url'] not in seed_urls])
    for url in seed_urls:
        pages.pop(url, None)
    queued = {p['url'] for p in queue}
    if parser_updated:
        # Parser upgrades explicitly retry unverified articles, including URLs
        # previously marked visited. Do not strand them behind archive traversal.
        repairs = []
        for item in store.unverified_articles(site['id']):
            previous = pages.pop(item['url'], {})
            repairs.append({**previous, **item, 'kind': 'article', 'label': previous.get('label','历史内容核验')})
        repair_urls = {p['url'] for p in repairs}
        queue = deque(repairs + [p for p in queue if p['url'] not in repair_urls])
        queued = {p['url'] for p in queue}
    inserted = attempts = 0
    started = time.monotonic()
    def checkpoint():
        store.save_coverage(site['id'], {'pages': list(pages.values()), 'pending': list(queue),
            'round_pages': attempts, 'round_new': inserted, 'scope': '公开栏目、翻页及文章原文核验', 'version': 2, 'metadata_version': 4})
    while queue and attempts < max_pages and time.monotonic()-started < max_seconds and not store.crawl_cancel.is_set():
        item = queue.popleft()
        url, label = item['url'], item['label']
        if url in pages:
            continue
        attempts += 1
        page = {**item, 'status': '正常', 'count': 0, 'error': ''}
        try:
            fetch_url = collection_target(root, url)
            if not robots.can_fetch(agent, fetch_url):
                raise ValueError('robots.txt 不允许采集此页面')
            delay = max(.15, float(robots.crawl_delay(agent) or 0))
            if delay > max_seconds - (time.monotonic()-started):
                queue.appendleft(item)
                attempts -= 1
                break
            time.sleep(delay)
            html, effective_url = fetch_html(opener, fetch_url, agent, max_bytes)
            if item.get('kind') == 'article':
                metadata = extract_article_metadata(html)
                if metadata['published_at']:
                    notice, created = store.upsert_live_notice(site['id'], metadata['title'] or item['title'], metadata.get('published_time') or metadata['published_at'], '校园服务', '', url,
                        date_verified=True, date_source=metadata['date_source'])
                    if item.get('section_url'):
                        store.add_notice_section(notice['id'], item['section_url'], label)
                    inserted += int(created); page['count'] = 1
                else:
                    notice, created = store.upsert_live_notice(site['id'], metadata['title'] or item['title'], '', '校园服务', '', url, date_source='原文未识别到发布时间')
                    if item.get('section_url'):
                        store.add_notice_section(notice['id'], item['section_url'], label)
                    inserted += int(created); page['count'] = 1
                    page['status'] = '待核验'
                    page['error'] = '原文未识别到可靠发布时间，不使用正文活动日期代替'
            else:
                dated = extract_notices(html, effective_url)
                for title, published, article_url in dated:
                    notice, created = store.upsert_live_notice(site['id'], title, published, '校园服务', '', canonical_url(article_url))
                    store.add_notice_section(notice['id'], effective_url, label)
                    inserted += int(created); page['count'] += 1
                children = discover_sections(html, effective_url, label)
                articles = discover_articles(html, effective_url)
                known = {x['url'] for x in articles}
                articles += [{'url':u,'title':t,'kind':'article'} for t,d,u in dated if u not in known]
                children += [{**child, 'label': label, 'section_url': effective_url} for child in articles]
                for child in children:
                    if child['url'] not in queued and child['url'] not in pages:
                        queued.add(child['url']); queue.append(child)
            page['effective_url'] = effective_url
        except (ValueError, OSError, LookupError) as exc:
            page['status'] = crawl_failure_status(exc)
            page['error'] = str(exc)
        pages[url] = page
        checkpoint()
    checkpoint()
    if not any(p['status'] == '正常' for p in pages.values()):
        raise ValueError(next(iter(pages.values()))['error'] if pages else '未检查任何页面')
    return inserted


def run_collection(store, site_id=None, claimed=False):
    if not claimed and not store.try_claim_crawl(site_id):
        return False
    sites = [store.get_site(site_id)] if site_id is not None else [s for s in store.list_sites() if s['enabled']]
    sites = [s for s in sites if s]
    waiting = deque(sites)
    completed = rounds = 0
    totals = {s['id']: 0 for s in sites}
    processed = {s['id']: 0 for s in sites}
    def progress():
        store.set_crawl_state(True, progress={'completed':completed,'total':len(sites),'batches':rounds,'site_id':site_id,'stopping':store.crawl_cancel.is_set()})
    progress()
    try:
        with ThreadPoolExecutor(max_workers=4, thread_name_prefix='swu-crawl') as executor:
            futures = {}
            while waiting or futures:
                while waiting and len(futures)<4 and not store.crawl_cancel.is_set():
                    site=waiting.popleft();futures[executor.submit(collect_site,store,site)]=site
                if not futures:break
                ready,_=wait(futures,timeout=1,return_when=FIRST_COMPLETED)
                for future in ready:
                    site=futures.pop(future);rounds+=1
                    try:
                        count=future.result();totals[site['id']]+=count
                        report=store.get_coverage(site['id'])
                        failed=sum(p['status']!='正常' for p in report['pages'])
                        pending=len(report['pending'])
                        processed[site['id']]+=report.get('round_pages',0)
                        limit=processed[site['id']]>=10000
                        again=pending and report.get('round_pages',0)>0 and not limit and not store.crawl_cancel.is_set()
                        note='；'.join(x for x in [f'{failed} 个页面异常或日期待核验' if failed else '', f'{pending} 个页面待继续' if pending else '', '本次已达10000页保护上限，进度已保存' if limit else ''] if x)
                        store.update_site_result(site['id'],'延迟' if failed or pending else '正常',note or None,totals[site['id']])
                        if again:waiting.append(site)
                        else:completed+=1
                    except Exception as exc:
                        store.update_site_result(site['id'],crawl_failure_status(exc),str(exc),totals[site['id']]);completed+=1
                    progress()
    finally:
        store.set_crawl_state(False, datetime.now().astimezone().isoformat(timespec='seconds'),
            {'completed':completed,'total':len(sites),'batches':rounds,'site_id':site_id,'stopped':store.crawl_cancel.is_set()})
    return True


def start_collection(store, site_id=None):
    if not store.try_claim_crawl(site_id):
        return False
    try:
        store.crawl_thread = threading.Thread(target=run_collection, args=(store, site_id, True), daemon=True)
        store.crawl_thread.start()
    except Exception:
        store.set_crawl_state(False)
        raise
    return True
