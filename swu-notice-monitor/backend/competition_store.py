"""Independent competition data; shares only the SQLite connection and lock."""
import json
import threading
from datetime import date, datetime, timedelta
from pathlib import Path


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


class CompetitionStore:
    def __init__(self, campus_store, catalog_path=None):
        self.db = campus_store.db
        self.lock = campus_store._lock
        self.cancel = threading.Event()
        self.thread = None
        self.catalog_path = Path(catalog_path or Path(__file__).resolve().parents[1] / 'data/competitions.json')
        self.catalog = json.loads(self.catalog_path.read_text(encoding='utf-8'))
        self.policy = self.catalog['policy']
        with self.lock:
            self.db.executescript('''
                CREATE TABLE IF NOT EXISTS competitions(id TEXT PRIMARY KEY, metadata TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS competition_sources(
                    id TEXT PRIMARY KEY, competition_id TEXT NOT NULL REFERENCES competitions(id),
                    config TEXT NOT NULL, status TEXT NOT NULL DEFAULT '未检查', error TEXT NOT NULL DEFAULT '',
                    last_checked TEXT, baseline INTEGER NOT NULL DEFAULT 0,
                    checkpoint TEXT NOT NULL DEFAULT '{}', active INTEGER NOT NULL DEFAULT 1);
                CREATE TABLE IF NOT EXISTS competition_notices(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    competition_id TEXT NOT NULL REFERENCES competitions(id), source_id TEXT NOT NULL REFERENCES competition_sources(id),
                    title TEXT NOT NULL, kind TEXT NOT NULL, published_at TEXT NOT NULL DEFAULT '',
                    date_verified INTEGER NOT NULL DEFAULT 0, url TEXT NOT NULL, attachments TEXT NOT NULL DEFAULT '[]',
                    read INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0,
                    collected_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(competition_id,url));
                CREATE INDEX IF NOT EXISTS competition_notice_date ON competition_notices(published_at DESC,id DESC);
                CREATE TABLE IF NOT EXISTS competition_subscriptions(
                    competition_id TEXT PRIMARY KEY REFERENCES competitions(id));
                CREATE TABLE IF NOT EXISTS competition_messages(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id INTEGER NOT NULL UNIQUE REFERENCES competition_notices(id),
                    created_at TEXT NOT NULL, read INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS competition_settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                INSERT OR IGNORE INTO competition_settings VALUES('interval_minutes','300');
                INSERT OR IGNORE INTO competition_settings VALUES('scheduler_enabled','true');
                CREATE TABLE IF NOT EXISTS competition_crawl_state(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), running INTEGER NOT NULL DEFAULT 0,
                    progress TEXT NOT NULL DEFAULT '{}', last_finished TEXT, resume INTEGER NOT NULL DEFAULT 0);
                INSERT OR IGNORE INTO competition_crawl_state(singleton) VALUES(1);
            ''')
            previous = dict(self.db.execute('SELECT * FROM competition_crawl_state').fetchone())
            progress = json.loads(previous['progress'])
            self.resume_requested = bool(previous['resume'] or (previous['running'] and not progress.get('stopping')))
            self.resume_id = progress.get('competition_id')
            self.db.execute('UPDATE competition_crawl_state SET running=0,resume=0')
            self.db.execute('UPDATE competition_sources SET active=0')
            for item in self.catalog['items']:
                metadata = {**item, 'awards': item.get('awards', self.policy['awards']),
                            'scores': item.get('scores', self.policy['score_groups'].get(item.get('score_group')))}
                self.db.execute('INSERT INTO competitions VALUES(?,?) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata',
                                (item['id'], json.dumps(metadata, ensure_ascii=False)))
                for index, config in enumerate(item['sources']):
                    source_id = f"{item['id']}:{index}"
                    old = self.db.execute('SELECT config FROM competition_sources WHERE id=?', (source_id,)).fetchone()
                    if old and json.loads(old['config']) != config:
                        self.db.execute("UPDATE competition_sources SET baseline=0,checkpoint='{}',status='未检查',error='' WHERE id=?", (source_id,))
                    self.db.execute('''INSERT INTO competition_sources(id,competition_id,config) VALUES(?,?,?)
                        ON CONFLICT(id) DO UPDATE SET config=excluded.config,active=1''',
                        (source_id, item['id'], json.dumps(config, ensure_ascii=False)))
            self.db.commit()

    def subscriptions(self):
        with self.lock:
            return {'competitions': [r[0] for r in self.db.execute('SELECT competition_id FROM competition_subscriptions ORDER BY competition_id')]}

    def save_subscriptions(self, ids):
        if not isinstance(ids, list) or any(not isinstance(x, str) for x in ids):
            raise ValueError('competitions 必须是赛事ID数组')
        ids = list(dict.fromkeys(ids))
        allowed = {x['id'] for x in self.catalog['items']}
        if not set(ids) <= allowed:
            raise ValueError('关注列表包含不存在的赛事')
        with self.lock:
            try:
                self.db.execute('BEGIN IMMEDIATE')
                self.db.execute('DELETE FROM competition_subscriptions')
                self.db.executemany('INSERT INTO competition_subscriptions VALUES(?)', [(x,) for x in ids])
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return self.subscriptions()

    def sources(self, competition_id=None):
        with self.lock:
            rows = self.db.execute('SELECT * FROM competition_sources WHERE active=1' +
                                   (' AND competition_id=?' if competition_id else '') + ' ORDER BY id',
                                   (competition_id,) if competition_id else ()).fetchall()
            return [{**dict(r), 'config': json.loads(r['config']), 'checkpoint': json.loads(r['checkpoint'])} for r in rows]

    def list_catalog(self, q='', group=''):
        followed = set(self.subscriptions()['competitions'])
        sources = self.sources()
        with self.lock:
            counts = dict(self.db.execute('SELECT competition_id,COUNT(*) FROM competition_notices GROUP BY competition_id'))
        items = []
        for original in self.catalog['items']:
            if group and original['group'] != group:
                continue
            if q.casefold() not in ' '.join([original['name'], original.get('current_name',''), *original.get('aliases', [])]).casefold():
                continue
            item = {**original, 'awards': original.get('awards',self.policy['awards']),
                    'scores': original.get('scores',self.policy['score_groups'].get(original.get('score_group'))),
                    'followed': original['id'] in followed, 'notice_count': counts.get(original['id'],0)}
            registered = [s for s in sources if s['competition_id'] == item['id']]
            item['official_url'] = original.get('official_url') or (registered[0]['config']['url'] if registered else None)
            item['last_checked'] = max((s['last_checked'] for s in registered if s['last_checked']), default=None)
            item['status'] = '待核验' if not registered else next((s['status'] for s in registered if s['status'] != '正常'), '正常')
            item['error'] = '；'.join(s['error'] for s in registered if s['error']) or original.get('pending_reason','')
            item['sources'] = [{**s['config'], 'id': s['id'], 'status': s['status'], 'error': s['error'],
                                'baseline': bool(s['baseline']), 'last_checked': s['last_checked']} for s in registered]
            items.append(item)
        return {'items': items, 'total': len(items), 'policy': self.policy}

    @staticmethod
    def page_args(limit, offset):
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            raise ValueError('limit 为1至100的整数，offset 为非负整数')

    @staticmethod
    def notice(row):
        if row is None:
            return None
        item = dict(row)
        for field in ('read','favorite','date_verified'):
            item[field] = bool(item[field])
        item['attachments'] = json.loads(item['attachments'])
        return item

    def list_notices(self, q='', competition='', kind='', tab='all', limit=10, offset=0):
        self.page_args(limit, offset)
        if tab not in ('all','following','favorite','unread'):
            raise ValueError('无效 tab 参数')
        conditions = ["(n.published_at='' OR substr(n.published_at,1,10)>=?)"]
        args = [(date.today()-timedelta(days=365)).isoformat()]
        if q:
            conditions.append('(n.title LIKE ? OR c.metadata LIKE ?)'); args += ['%'+q+'%']*2
        for field, value in [('competition_id',competition),('kind',kind)]:
            if value:
                conditions.append('n.'+field+'=?'); args.append(value)
        if tab == 'following':
            conditions.append('n.competition_id IN (SELECT competition_id FROM competition_subscriptions)')
        elif tab == 'favorite':
            conditions.append('n.favorite=1')
        elif tab == 'unread':
            conditions.append('n.read=0')
        joined = ' FROM competition_notices n JOIN competitions c ON c.id=n.competition_id WHERE '+' AND '.join(conditions)
        with self.lock:
            total = self.db.execute('SELECT COUNT(*)'+joined, args).fetchone()[0]
            rows = self.db.execute("SELECT n.*,json_extract(c.metadata,'$.name') AS competition_name"+joined+
                ' ORDER BY n.published_at DESC,n.id DESC LIMIT ? OFFSET ?', [*args,limit,offset]).fetchall()
        return {'items':[self.notice(r) for r in rows], 'total':total}

    def get_notice(self, id):
        with self.lock:
            return self.notice(self.db.execute("SELECT n.*,json_extract(c.metadata,'$.name') AS competition_name FROM competition_notices n JOIN competitions c ON c.id=n.competition_id WHERE n.id=?", (id,)).fetchone())

    def update_notice(self, id, changes):
        if not changes or not set(changes) <= {'read','favorite'} or any(type(x) is not bool for x in changes.values()):
            raise ValueError('只支持 read/favorite 布尔值')
        with self.lock:
            self.db.execute('UPDATE competition_notices SET '+','.join(k+'=?' for k in changes)+' WHERE id=?', [*changes.values(),id])
            if changes.get('read'):
                self.db.execute('UPDATE competition_messages SET read=1 WHERE notice_id=?',(id,))
            self.db.commit()
        return self.get_notice(id)

    def upsert_notice(self, source, item):
        published = item.get('published_at','')
        if published and published[:10] < (date.today()-timedelta(days=365)).isoformat():
            return None, False
        with self.lock:
            prior = self.db.execute('SELECT * FROM competition_notices WHERE competition_id=? AND url=?',
                                    (source['competition_id'],item['url'])).fetchone()
            timestamp = now()
            if prior:
                # An undated list refresh must not erase verified detail metadata.
                self.db.execute('''UPDATE competition_notices SET title=?,kind=?,published_at=?,date_verified=?,attachments=?,updated_at=? WHERE id=?''',
                    (item['title'],item['kind'],published or prior['published_at'],bool(published or prior['date_verified']),
                     json.dumps(item.get('attachments') or json.loads(prior['attachments']),ensure_ascii=False),timestamp,prior['id']))
                id = prior['id']
            else:
                cur = self.db.execute('''INSERT INTO competition_notices(competition_id,source_id,title,kind,published_at,date_verified,url,attachments,collected_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?)''', (source['competition_id'],source['id'],item['title'],item['kind'],published,bool(published),item['url'],json.dumps(item.get('attachments',[]),ensure_ascii=False),timestamp,timestamp))
                id = cur.lastrowid
                baseline = self.db.execute('SELECT baseline FROM competition_sources WHERE id=?',(source['id'],)).fetchone()[0]
                followed = self.db.execute('SELECT 1 FROM competition_subscriptions WHERE competition_id=?',(source['competition_id'],)).fetchone()
                if baseline and followed:
                    self.db.execute('INSERT OR IGNORE INTO competition_messages(notice_id,created_at) VALUES(?,?)',(id,timestamp))
            self.db.commit()
        return self.get_notice(id), prior is None

    def list_messages(self, limit=10, offset=0):
        self.page_args(limit, offset)
        with self.lock:
            total, unread = self.db.execute('SELECT COUNT(*),COALESCE(SUM(read=0),0) FROM competition_messages').fetchone()
            rows = self.db.execute('''SELECT m.id,m.notice_id,m.created_at,m.read,n.title,n.competition_id,
                json_extract(c.metadata,'$.name') AS competition_name FROM competition_messages m
                JOIN competition_notices n ON n.id=m.notice_id JOIN competitions c ON c.id=n.competition_id
                ORDER BY m.id DESC LIMIT ? OFFSET ?''',(limit,offset)).fetchall()
        return {'items':[{**dict(r),'read':bool(r['read'])} for r in rows], 'total':total,'unread':unread}

    def read_messages(self, id=None):
        with self.lock:
            cur = self.db.execute('UPDATE competition_messages SET read=1'+(' WHERE id=?' if id is not None else ''), (id,) if id is not None else ())
            self.db.commit()
            return cur.rowcount

    def settings(self):
        with self.lock:
            return {r['key']:json.loads(r['value']) for r in self.db.execute('SELECT * FROM competition_settings')}

    def save_settings(self, value):
        if set(value) != {'interval_minutes','scheduler_enabled'} or type(value['scheduler_enabled']) is not bool or type(value['interval_minutes']) is not int or not 5<=value['interval_minutes']<=1440:
            raise ValueError('需要 scheduler_enabled 布尔值及5至1440分钟的 interval_minutes')
        with self.lock:
            self.db.executemany('UPDATE competition_settings SET value=? WHERE key=?',[(json.dumps(v),k) for k,v in value.items()])
            self.db.commit()
        return self.settings()

    def crawl_state(self):
        with self.lock:
            r = self.db.execute('SELECT * FROM competition_crawl_state').fetchone()
            return {**json.loads(r['progress']), 'running':bool(r['running']), 'last_finished':r['last_finished']}

    def claim(self, competition_id):
        with self.lock:
            if self.crawl_state()['running']:
                return False
            self.cancel.clear()
            self.db.execute('UPDATE competition_crawl_state SET running=1,resume=0,progress=?',
                (json.dumps({'competition_id':competition_id,'completed':0,'total':len(self.sources(competition_id)),'stopping':False}),))
            self.db.commit()
            return True

    def progress(self, value, finished=False):
        with self.lock:
            self.db.execute('UPDATE competition_crawl_state SET progress=?,running=?,last_finished=COALESCE(?,last_finished)',
                (json.dumps(value),not finished,now() if finished else None))
            self.db.commit()

    def checkpoint(self, source_id, value, status, error='', complete=False):
        with self.lock:
            self.db.execute('''UPDATE competition_sources SET checkpoint=?,status=?,error=?,last_checked=?,baseline=CASE WHEN ? THEN 1 ELSE baseline END WHERE id=?''',
                (json.dumps(value,ensure_ascii=False),status,error,now(),complete,source_id))
            self.db.commit()

    def stop(self, resume=False):
        with self.lock:
            state = self.crawl_state()
            if state['running']:
                state['stopping'] = True
                self.progress({k:v for k,v in state.items() if k not in ('running','last_finished')})
                self.db.execute('UPDATE competition_crawl_state SET resume=?',(resume,)); self.db.commit()
                self.cancel.set()
