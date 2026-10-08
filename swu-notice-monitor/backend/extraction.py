"""Structural HTML extraction: publication metadata is separate from article body."""
import re
from datetime import datetime, date
from html.parser import HTMLParser
from urllib.parse import urlsplit
from .urls import resolve_page_link

DATE = re.compile(r'(?<!\d)((?:19|20)\d{2})\s*[-年/.]\s*(\d{1,2})\s*[-月/.]\s*(\d{1,2})(?!\d)日?')
VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}

def dates(text):
    for m in DATE.finditer(text):
        try: yield date(*map(int,m.groups())).isoformat()
        except ValueError: pass

def normalized(text): return ' '.join(text.split())

class Node:
    def __init__(self,tag='',attrs=None,parent=None):
        self.tag=tag; self.attrs=dict(attrs or []); self.parent=parent; self.children=[]
    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child,Node): yield from child.walk()
    def text(self,skip=None):
        if self.tag in ('script','style','noscript') or (skip and skip(self)): return ''
        return ' '.join(c.text(skip) if isinstance(c,Node) else c for c in self.children)
    @property
    def cls(self): return (self.attrs.get('class','')+' '+self.attrs.get('id','')).lower()

class Tree(HTMLParser):
    def __init__(self,html):
        super().__init__();self.root=Node();self.stack=[self.root];self.feed(html)
    def handle_starttag(self,tag,attrs):
        n=Node(tag,attrs,self.stack[-1]);self.stack[-1].children.append(n)
        if tag not in VOID:self.stack.append(n)
    def handle_endtag(self,tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag==tag:del self.stack[i:];break
    def handle_data(self,data):self.stack[-1].children.append(data)

def is_date(n):
    return n.tag=='time' or bool(re.search(r'date|time|\bsj\b|\byear\b|\bmonth\b|\bday\b',n.cls))
def is_body(n):
    return bool(re.search(r'v_news_content|vsb_content|article[-_]body|article[-_]content|news[-_]content|\bsummary\b|\bintro\b|\bdesc(?:ription)?\b',n.cls))

def in_body(n):
    while n:
        if is_body(n):return True
        n=n.parent
    return False

def node_date(n):
    text=normalized(n.text())
    result=next(dates(n.attrs.get('datetime','')+' '+text),None)
    if result:return result
    # Day / year-month and month-day / [year] blocks, without joining digits.
    for pattern,order in [(r'^(\d{1,2})\s+((?:19|20)\d{2})[-/.](\d{1,2})$',(2,3,1)),(r'^(\d{1,2})[-/.](\d{1,2})\s*\[?((?:19|20)\d{2})\]?$',(3,1,2))]:
        m=re.match(pattern,text)
        if m:
            try:return date(*(int(m.group(i)) for i in order)).isoformat()
            except ValueError:return None
    return None

def anchor_title(a):
    if a.attrs.get('title'):return normalized(a.attrs['title'])
    for n in a.walk():
        if n.tag in ('h1','h2','h3','h4') or re.search(r'(?:^|[\s_-])(?:title|tit|headline|bt)(?:$|[\s_-])',n.cls):
            t=normalized(n.text());
            if t and not re.fullmatch(r'[\d\s年月日./\-\[\]:]+',t):return t
    blocks=[n for n in a.walk() if n.tag in ('p','div') and not is_date(n) and not is_body(n)]
    for n in blocks:
        t=normalized(n.text(lambda x:is_date(x) or is_body(x)))
        if t and not DATE.fullmatch(t):return t
    return normalized(a.text(lambda x:is_date(x) or is_body(x)))

def article_url(url):
    p=urlsplit(url)
    return bool(re.search(r'/(?:info|content|news|article)(?:/|[_-]).*\.(?:html?|shtml)$',p.path,re.I) or re.search(r'(?:newsid|articleid|infoid|contentid|wbnewsid)=\d+',p.query,re.I))

def discover_articles(html,base_url):
    root=Tree(html).root;out=[];seen=set()
    for a in root.walk():
        if a.tag!='a':continue
        url=resolve_page_link(base_url,a.attrs.get('href',''))
        if not url:continue
        if url in seen or not article_url(url) or urlsplit(url).hostname!=urlsplit(base_url).hostname:continue
        title=anchor_title(a)
        if not title or re.fullmatch(r'\d+|首页|尾页|末页|上(?:一)?页|下(?:一)?页|Next|Previous|[<>«»‹›]+',title,re.I):continue
        seen.add(url);out.append({'url':url,'title':title,'kind':'article'})
    return out

def extract_notices(html,base_url):
    root=Tree(html).root;out=[];seen=set()
    for a in root.walk():
        if a.tag!='a':continue
        href=a.attrs.get('href','');url=resolve_page_link(base_url,href)
        if not url:continue
        p=urlsplit(url)
        title=anchor_title(a)
        if not href or href.startswith(('#','javascript:')) or p.hostname!=urlsplit(base_url).hostname or p.scheme not in ('http','https') or p.path in ('','/') or len(title)<2 or url in seen:continue
        if title in ('首页','更多','查看详情','上一页','下一页'):continue
        current=a;published=None
        for depth in range(5):
            if current is None:break
            anchors=[x for x in current.walk() if x.tag=='a' and anchor_title(x) not in ('更多','查看详情')]
            if len({x.attrs.get('href') for x in anchors})>1:break
            for n in current.walk():
                if is_date(n) and not in_body(n):
                    published=node_date(n)
                    if published:break
            if not published:
                # Date-only siblings, never dates from summaries or article titles.
                for n in current.walk():
                    t=normalized(n.text())
                    if n is not a and not any(x.tag=='a' for x in n.walk()) and not in_body(n):
                        if re.fullmatch(r'[\d\s年月日./\-\[\]:]+',t):
                            published=node_date(n)
                            if published:break
                if not published and current.tag in ('li','tr'):
                    outside=normalized(current.text(lambda n:n.tag=='a' or is_body(n)))
                    if DATE.fullmatch(outside):published=next(dates(outside),None)
                    if not published:
                        temp=Node();temp.children=[outside];published=node_date(temp)
            if published:break
            current=current.parent
        if published:
            seen.add(url);out.append((title,published,url))
    return out

def extract_article_metadata(html, section=''):
    root=Tree(html).root;nodes=list(root.walk());title='';published=None;source='';date_text=''
    def strict_body(n):
        return bool(re.search(r'(?:^|\s)(?:v_news_content|vsb_content[^\s]*|article[-_]body|news[-_]content|summary|intro|description)(?:\s|$)',n.cls))
    def excluded(n):
        while n:
            if strict_body(n) or n.tag in ('script','style','nav','footer','aside'):return True
            n=n.parent
        return False
    header=[n for n in nodes if not excluded(n)]
    for n in nodes:
        if n.tag!='meta':continue
        key=(n.attrs.get('name') or n.attrs.get('property') or n.attrs.get('itemprop') or '').lower()
        value=n.attrs.get('content','')
        if key in ('articletitle','og:title','headline') and not title:title=normalized(value)
        if not excluded(n) and key in ('pubdate','publishdate','publishedtime','article:published_time','datepublished','dc.date.issued'):
            candidate=next(dates(value),None)
            if candidate:published=candidate;source='原文发布元数据';date_text=value
    if not title:
        doc_title=next((normalized(n.text()) for n in nodes if n.tag=='title'),'')
        headings=[normalized(n.text()) for n in header if (n.tag in ('h1','h2') or re.search(r'(?:^|\s)(?:column-name|article-title|news-title|arti_title)(?:\s|$)',n.cls)) and 4<=len(normalized(n.text()))<=300]
        title=next((x for x in headings if x in doc_title), '') or (headings[-1] if headings else re.split(r'[-_—]\s*西南大学',doc_title)[0])
    # Generic article-content wrappers contain both metadata and body. Exclude
    # only actual body subtrees; never stop traversal at a layout container.
    if not published:
        for n in header:
            if n.tag not in ('span','p','div','td','time'):continue
            text=normalized(n.text())
            if len(text)>300 or any(strict_body(x) for x in n.walk()):continue
            m=re.search(r'(?:发布(?:时间|日期)|发表(?:时间|日期)|日期)\s*[:：]\s*('+DATE.pattern+r')',text)
            if m:
                published=next(dates(m.group(1)),None);source='原文发布时间';date_text=text[m.start(1):];break
    if not published:
        # Header metadata often groups a date with author/reviewer/views.
        for n in header:
            text=normalized(n.text())
            if len(text)>250 or any(strict_body(x) for x in n.walk()):continue
            if (is_date(n) and n.attrs.get('datetime')) or (re.search(r'作者|审核|浏览|来源',text) and len(list(dates(text)))==1):
                candidate=node_date(n)
                if candidate:
                    published=candidate;source='原文信息栏';date_text=n.attrs.get('datetime','') or text;break
    if published and published>date.today().isoformat():published=None;source='原文日期异常，待核验'
    published_time=None
    if published:
        match=DATE.search(date_text)
        clock=re.match(r'[T\s]+([01]?\d|2[0-3]):([0-5]\d)(?::[0-5]\d)?',date_text[match.end():]) if match else None
        if clock:published_time=f'{published} {int(clock[1]):02d}:{clock[2]}'
    summary=article_summary(nodes)
    return {'title':title,'published_at':published,'published_time':published_time,'date_source':source,
            'summary':summary,'category':classify_notice(title, section, summary)}


CATEGORY_RULES = (
    ('国际交流', r'国际交流|出国|出境|境外|留学|访学|交换生|海外'),
    ('招生就业', r'招生|就业|招聘|宣讲会|双选会|录取|推免|招聘会'),
    ('竞赛活动', r'竞赛|比赛|大赛|运动会|文艺|志愿|社团|征文'),
    ('学术讲座', r'学术|讲座|论坛|研讨会|报告会'),
    ('教学教务', r'教学|教务|选课|补退选|课程|考试|培养|学籍|毕业|成绩|学位|研究生培养'),
)


def classify_notice(title, section='', summary=''):
    # Title is strongest evidence; section and body are progressively weaker.
    for text in (title, section, summary):
        for category, pattern in CATEGORY_RULES:
            if re.search(pattern, text):
                return category
    return '校园服务'


def article_summary(nodes):
    for n in nodes:
        if n.tag == 'meta' and (n.attrs.get('name') or n.attrs.get('property') or '').lower() in ('description', 'og:description'):
            text = normalized(n.attrs.get('content', ''))
            if text:
                return text[:240]
    bodies = [n for n in nodes if re.search(r'(?:^|\s)(?:v_news_content|vsb_content[^\s]*|article[-_]body|news[-_]content)(?:\s|$)', n.cls)]
    if not bodies:
        bodies = [n for n in nodes if re.search(r'(?:^|\s)article[-_]content(?:\s|$)', n.cls)]
    for body in bodies:
        text = normalized(body.text(lambda n: n.tag in ('nav', 'footer', 'aside', 'h1', 'h2', 'time')
                                    or is_date(n) or bool(re.search(r'column-name|article-title|news-title', n.cls))))
        if text:
            return text[:240]
    return ''
