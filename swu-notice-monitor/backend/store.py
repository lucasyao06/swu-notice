import json
import sqlite3
import threading
from datetime import date, datetime, timedelta
from pathlib import Path


DEMO_TODAY = date(2026, 9, 22)
ALLOWED_CATEGORIES = {"教学教务", "学术讲座", "竞赛活动", "招生就业", "国际交流", "校园服务"}
DEMO_NOTICES = [
    (11, "关于本学期课程补退选安排的通知", "2026-09-22 10:20", "教学教务", "本学期课程补退选工作现已开放，请同学们在规定时间内登录教务系统核对培养方案、课程容量与上课时间，完成选课后及时保存并确认课表。逾期调整请按学院要求提交申请。", "demo://notice/1"),
    (51, "人工智能与软件工程学术交流活动", "2026-09-22 09:40", "学术讲座", "学院将举办人工智能与软件工程专题学术交流活动，内容涵盖大模型工程实践、软件质量保障与科研经验分享，欢迎相关专业师生按时参加。", "demo://notice/2"),
    (12, "研究生培养相关材料提交提醒", "2026-09-21 16:30", "教学教务", "请研究生按照培养环节要求检查个人材料，完成导师签字与学院审核，并在截止时间前提交。材料名称、格式和办理地点以培养单位通知为准。", "demo://notice/3"),
    (67, "自习空间开放与预约服务说明", "2026-09-21 14:00", "校园服务", "图书馆自习空间按开放时间提供预约服务。读者可通过预约入口选择时段与座位，到馆后按要求签到；如行程变化，请及时取消预约。", "demo://notice/4"),
    (28, "学生国际交流项目说明会", "2026-09-20 15:30", "国际交流", "学院将举行学生国际交流项目说明会，介绍项目类型、申请条件、材料准备与时间安排，并设置现场答疑环节，有意向的同学可提前准备相关问题。", "demo://notice/5"),
]


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path, sites_path):
        self.db_path = Path(db_path)
        first_init = not self.db_path.exists() or self.db_path.stat().st_size == 0
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.crawl_cancel = threading.Event()
        self.crawl_thread = None
        self.resume_requested = False
        self.resume_site_id = None
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        with self._lock:
            self.db.executescript("""
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS sites(
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
                    type TEXT NOT NULL, group_name TEXT NOT NULL, note TEXT NOT NULL,
                    enabled INTEGER NOT NULL DEFAULT 0, list_url TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '未接入', last_checked TEXT,
                    new_count INTEGER NOT NULL DEFAULT 0, error TEXT
                );
                CREATE TABLE IF NOT EXISTS notices(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, source_id INTEGER NOT NULL,
                    title TEXT NOT NULL, published_at TEXT NOT NULL, category TEXT NOT NULL,
                    summary TEXT NOT NULL, url TEXT NOT NULL, is_demo INTEGER NOT NULL,
                    read INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL, UNIQUE(source_id, url, is_demo),
                    FOREIGN KEY(source_id) REFERENCES sites(id)
                );
                CREATE TABLE IF NOT EXISTS site_coverage(
                    site_id INTEGER PRIMARY KEY REFERENCES sites(id), report TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS notice_sections(
                    notice_id INTEGER NOT NULL REFERENCES notices(id),
                    url TEXT NOT NULL, label TEXT NOT NULL, PRIMARY KEY(notice_id,url)
                );
                CREATE TABLE IF NOT EXISTS subscriptions(
                    kind TEXT NOT NULL, value TEXT NOT NULL, PRIMARY KEY(kind,value)
                );
                CREATE TABLE IF NOT EXISTS preferences(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(
                    id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                    source_name TEXT NOT NULL, created_at TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT '已送达', read INTEGER NOT NULL DEFAULT 0,
                    notice_id INTEGER NOT NULL UNIQUE, is_demo INTEGER NOT NULL,
                    FOREIGN KEY(notice_id) REFERENCES notices(id)
                );
                CREATE TABLE IF NOT EXISTS crawl_state(
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1), running INTEGER NOT NULL DEFAULT 0,
                    last_finished TEXT, progress TEXT NOT NULL DEFAULT '{}'
                );
                INSERT OR IGNORE INTO crawl_state(singleton) VALUES(1);
                INSERT OR IGNORE INTO preferences(key,value) VALUES('interval_minutes','60');
                INSERT OR IGNORE INTO preferences(key,value) VALUES('scheduler_enabled','false');
                INSERT OR IGNORE INTO preferences(key,value) VALUES('in_app','true');
            """)
            columns = {r[1] for r in self.db.execute('PRAGMA table_info(notices)')}
            if 'date_verified' not in columns:
                self.db.execute('ALTER TABLE notices ADD COLUMN date_verified INTEGER NOT NULL DEFAULT 0')
                self.db.execute("ALTER TABLE notices ADD COLUMN date_source TEXT NOT NULL DEFAULT '待原文核验'")
            self.db.execute("UPDATE sites SET status='未接入' WHERE status='未连接'")
            previous = self.db.execute('SELECT running,progress FROM crawl_state WHERE singleton=1').fetchone()
            marker = self.db.execute("SELECT value FROM preferences WHERE key='resume_crawl'").fetchone()
            resume = json.loads(marker['value']) if marker else None
            old_progress = json.loads(previous['progress'])
            self.resume_requested = bool(resume is not None or (previous['running'] and not old_progress.get('stopping')))
            self.resume_site_id = (resume if resume is not None else old_progress).get('site_id')
            self.db.execute("DELETE FROM preferences WHERE key='resume_crawl'")
            self.db.execute("UPDATE crawl_state SET running=0 WHERE singleton=1")
            self.db.commit()
        self.import_sites(sites_path)
        self._seed_demo()
        self._initialize_subscriptions(first_init)

    def close(self):
        with self._lock:
            self.db.close()

    def import_sites(self, path):
        records = json.loads(Path(path).read_text(encoding="utf-8"))
        with self._lock:
            self.db.executemany("""
                INSERT INTO sites(id,name,url,type,group_name,note) VALUES(?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url,
                type=excluded.type,group_name=excluded.group_name,note=excluded.note
            """, [(x["id"], x["name"], x["url"], x["type"], x["group"], x.get("note", "")) for x in records])
            self.db.execute("UPDATE sites SET status='未接入' WHERE status='未连接'")
            self.db.commit()

    def _seed_demo(self):
        with self._lock:
            self.db.executemany("""
                INSERT INTO notices(source_id,title,published_at,category,summary,url,is_demo,created_at)
                VALUES(?,?,?,?,?,?,1,?)
                ON CONFLICT(source_id,url,is_demo) DO UPDATE SET title=excluded.title,
                published_at=excluded.published_at,category=excluded.category,summary=excluded.summary
            """, [(*row, _now()) for row in DEMO_NOTICES])
            demo_rows = self.db.execute("""SELECT n.id,n.title,s.name,n.published_at
                FROM notices n JOIN sites s ON s.id=n.source_id
                WHERE n.is_demo=1 ORDER BY n.published_at DESC LIMIT 3""").fetchall()
            statuses = ("已送达", "待发送", "失败")
            self.db.executemany("""INSERT INTO messages
                (title,source_name,created_at,status,notice_id,is_demo)
                VALUES(?,?,?,?,?,1) ON CONFLICT(notice_id) DO UPDATE SET
                title=excluded.title,source_name=excluded.source_name,created_at=excluded.created_at,
                status=excluded.status,is_demo=1""",
                [(r["title"], r["name"], r["published_at"], statuses[i], r["id"]) for i,r in enumerate(demo_rows)])
            self.db.commit()

    def _initialize_subscriptions(self, first_init):
        if not first_init:
            return
        with self._lock:
            self.db.executemany("INSERT OR IGNORE INTO subscriptions(kind,value) VALUES(?,?)", [
                ("source", "11"), ("source", "67"), ("source", "28"),
                ("keyword", "人工智能"), ("keyword", "课程补退选"),
                ("category", "教学教务"), ("category", "国际交流"),
            ])
            self.db.commit()

    @staticmethod
    def _site(row):
        out = dict(row)
        out["group"] = out.pop("group_name")
        out["enabled"] = bool(out["enabled"])
        return out

    def list_sites(self):
        with self._lock:
            items = [self._site(r) for r in self.db.execute("SELECT * FROM sites ORDER BY id")]
            for item in items:
                report = self.get_coverage(item['id'])
                pages = report['pages']
                item['coverage'] = {'checked': len(pages), 'pending': len(report['pending']),
                    'failed': sum(p['status'] != '正常' for p in pages),
                    'sections': len(set(p['label'] for p in pages)), 'updated_at': report.get('updated_at')}
            return items

    def get_site(self, site_id):
        with self._lock:
            row = self.db.execute("SELECT * FROM sites WHERE id=?", (site_id,)).fetchone()
            return self._site(row) if row else None

    def set_all_sites_enabled(self, enabled):
        if type(enabled) is not bool:
            raise ValueError("enabled 必须是布尔值")
        with self._lock:
            self.db.execute("UPDATE sites SET enabled=?", (int(enabled),))
            self.db.commit()
        return self.list_sites()

    def update_site(self, site_id, enabled, list_url):
        with self._lock:
            cur = self.db.execute("UPDATE sites SET enabled=?,list_url=? WHERE id=?", (int(enabled), list_url, site_id))
            self.db.commit()
            return self.get_site(site_id) if cur.rowcount else None

    @staticmethod
    def _notice(row):
        out = dict(row)
        out["is_demo"] = bool(out["is_demo"])
        out["read"] = bool(out["read"])
        out["favorite"] = bool(out["favorite"])
        return out

    def get_notice(self, notice_id):
        with self._lock:
            row = self.db.execute("""SELECT n.*,s.name source_name,s.type source_type, (SELECT group_concat(DISTINCT label) FROM notice_sections WHERE notice_id=n.id) AS sections
                FROM notices n JOIN sites s ON s.id=n.source_id WHERE n.id=?""", (notice_id,)).fetchone()
            return self._notice(row) if row else None

    def list_notices(self, mode="demo", q="", type="", category="", read="all", source="",
                     period="all", start="", end="", subscribed=False, limit=None, offset=0):
        if limit is not None and (limit.__class__ is not int or not 1 <= limit <= 100):
            raise ValueError("limit 必须在 1 到 100 之间")
        if offset.__class__ is not int or offset < 0:
            raise ValueError("offset 必须是非负整数")
        clauses = ["n.is_demo=?"]
        args = [1 if mode == "demo" else 0]
        if q:
            clauses.append("(n.title LIKE ? OR n.summary LIKE ? OR s.name LIKE ?)")
            args += [f"%{q}%"] * 3
        if type:
            clauses.append("s.type=?"); args.append(type)
        if category:
            clauses.append("n.category=?"); args.append(category)
        if source:
            clauses.append("n.source_id=?"); args.append(int(source))
        if read == "unread": clauses.append("n.read=0")
        elif read == "read": clauses.append("n.read=1")
        elif read == "favorite": clauses.append("n.favorite=1")
        today = DEMO_TODAY if mode == "demo" else date.today()
        if period == "today": start = end = today.isoformat()
        elif period == "week": start, end = (today - timedelta(days=6)).isoformat(), today.isoformat()
        elif period == "month": start, end = today.replace(day=1).isoformat(), today.isoformat()
        if period in ("today", "week", "month", "custom"):
            if start: clauses.append("substr(n.published_at,1,10)>=?"); args.append(start)
            if end: clauses.append("substr(n.published_at,1,10)<=?"); args.append(end)
        if subscribed:
            clauses.append("""(EXISTS(SELECT 1 FROM subscriptions x WHERE x.kind='source' AND x.value=CAST(n.source_id AS TEXT))
                OR EXISTS(SELECT 1 FROM subscriptions x WHERE x.kind='category' AND x.value=n.category)
                OR EXISTS(SELECT 1 FROM subscriptions x WHERE x.kind='keyword' AND n.title LIKE '%'||x.value||'%'))""")
        sql = """SELECT n.*,s.name source_name,s.type source_type, (SELECT group_concat(DISTINCT label) FROM notice_sections WHERE notice_id=n.id) AS sections FROM notices n
            JOIN sites s ON s.id=n.source_id WHERE """ + " AND ".join(clauses) + " ORDER BY n.published_at DESC,n.id DESC"
        with self._lock:
            if limit is not None:
                count_sql = "SELECT COUNT(*) FROM notices n JOIN sites s ON s.id=n.source_id WHERE " + " AND ".join(clauses)
                total = self.db.execute(count_sql, args).fetchone()[0]
                items = [self._notice(r) for r in self.db.execute(sql + " LIMIT ? OFFSET ?", args + [limit, offset])]
            else:
                items = [self._notice(r) for r in self.db.execute(sql, args)]
                total = len(items)
        return {"items": items, "total": total}

    def update_notice(self, notice_id, read=None, favorite=None):
        fields, args = [], []
        if read is not None: fields.append("read=?"); args.append(int(read))
        if favorite is not None: fields.append("favorite=?"); args.append(int(favorite))
        if not fields: return self.get_notice(notice_id)
        with self._lock:
            args.append(notice_id)
            cur = self.db.execute(f"UPDATE notices SET {','.join(fields)} WHERE id=?", args)
            self.db.commit()
            return self.get_notice(notice_id) if cur.rowcount else None

    def get_subscriptions(self):
        result = {"sources": [], "keywords": [], "categories": []}
        with self._lock:
            for row in self.db.execute("SELECT kind,value FROM subscriptions ORDER BY value"):
                key = {"source": "sources", "keyword": "keywords", "category": "categories"}[row["kind"]]
                result[key].append(int(row["value"]) if row["kind"] == "source" else row["value"])
            result["in_app"] = json.loads(self.db.execute("SELECT value FROM preferences WHERE key='in_app'").fetchone()[0])
        return result

    def save_subscriptions(self, sources, keywords, categories, in_app):
        if type(in_app) is not bool:
            raise ValueError("in_app 必须是布尔值")
        if not all(isinstance(x, list) for x in (sources, keywords, categories)):
            raise ValueError("订阅项必须是数组")
        if any(len(x) > 50 for x in (sources, keywords, categories)):
            raise ValueError("每类订阅最多 50 项")
        if any(type(x) is not int or x <= 0 for x in sources):
            raise ValueError("来源订阅必须是正整数")
        normalized_sources = list(dict.fromkeys(sources))
        if normalized_sources:
            placeholders = ",".join("?" for _ in normalized_sources)
            with self._lock:
                found = self.db.execute(f"SELECT COUNT(*) FROM sites WHERE id IN ({placeholders})", normalized_sources).fetchone()[0]
            if found != len(normalized_sources):
                raise ValueError("来源订阅包含不存在的站点")
        if any(not isinstance(x, str) for x in keywords):
            raise ValueError("关键词订阅必须是字符串")
        normalized_keywords = list(dict.fromkeys(x.strip() for x in keywords))
        if any(not x or len(x) > 50 for x in normalized_keywords):
            raise ValueError("关键词长度必须在 1 到 50 个字符之间")
        if any(not isinstance(x, str) for x in categories):
            raise ValueError("分类订阅必须是字符串")
        normalized_categories = list(dict.fromkeys(x.strip() for x in categories))
        if any(x not in ALLOWED_CATEGORIES for x in normalized_categories):
            raise ValueError("分类订阅包含不支持的分类")
        rows = ([('source', str(x)) for x in normalized_sources] +
                [('keyword', x) for x in normalized_keywords] +
                [('category', x) for x in normalized_categories])
        with self._lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                self.db.execute("DELETE FROM subscriptions")
                self.db.executemany("INSERT INTO subscriptions(kind,value) VALUES(?,?)", rows)
                self.db.execute("UPDATE preferences SET value=? WHERE key='in_app'", (json.dumps(in_app),))
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return self.get_subscriptions()

    def _matches_subscription(self, source_id, title, category):
        sub = self.get_subscriptions()
        return source_id in sub["sources"] or category in sub["categories"] or any(k in title for k in sub["keywords"])

    def upsert_live_notice(self, source_id, title, published_at, category, summary, url, date_verified=False, date_source="列表日期，待原文核验"):
        with self._lock:
            before = self.db.total_changes
            self.db.execute("""INSERT OR IGNORE INTO notices(source_id,title,published_at,category,summary,url,is_demo,created_at)
                VALUES(?,?,?,?,?,?,0,?)""", (source_id,title,published_at,category,summary,url,_now()))
            inserted = self.db.total_changes > before
            row = self.db.execute("SELECT id,date_verified FROM notices WHERE source_id=? AND url=? AND is_demo=0", (source_id,url)).fetchone()
            if not inserted and (date_verified or not row["date_verified"]):
                # Re-crawling repairs extracted metadata without replacing the
                # notice ID, user state or creating another delivery.
                self.db.execute("UPDATE notices SET title=?,published_at=?,summary=? WHERE id=?",
                                (title, published_at, summary, row["id"]))
                self.db.execute("UPDATE messages SET title=? WHERE notice_id=?", (title, row["id"]))
            if date_verified:
                self.db.execute('UPDATE notices SET date_verified=1,date_source=? WHERE id=?', (date_source,row['id']))
            elif not row['date_verified']:
                self.db.execute('UPDATE notices SET date_source=? WHERE id=?', (date_source,row['id']))
            notice = self.get_notice(row["id"])
            if inserted and self.get_subscriptions()["in_app"] and self._matches_subscription(source_id,title,category):
                self.db.execute("""INSERT OR IGNORE INTO messages(title,source_name,created_at,notice_id,is_demo)
                    VALUES(?,?,?,?,0)""", (title, notice["source_name"], _now(), notice["id"]))
            self.db.commit()
            return notice, inserted

    def list_messages(self, mode="demo"):
        is_demo = 1 if mode == "demo" else 0
        with self._lock:
            rows = [dict(r) for r in self.db.execute("SELECT * FROM messages WHERE is_demo=? ORDER BY created_at DESC,id DESC", (is_demo,))]
        for row in rows: row["read"], row["is_demo"] = bool(row["read"]), bool(row["is_demo"])
        return {"items": rows, "unread": sum(not x["read"] for x in rows)}

    def read_message(self, message_id):
        with self._lock:
            cur = self.db.execute("UPDATE messages SET read=1 WHERE id=?", (message_id,)); self.db.commit()
            return bool(cur.rowcount)

    def get_settings(self):
        with self._lock:
            values = dict(self.db.execute("SELECT key,value FROM preferences WHERE key IN ('interval_minutes','scheduler_enabled')"))
        return {"interval_minutes": int(values["interval_minutes"]), "scheduler_enabled": json.loads(values["scheduler_enabled"])}

    def save_settings(self, interval_minutes, scheduler_enabled):
        with self._lock:
            self.db.execute("UPDATE preferences SET value=? WHERE key='interval_minutes'", (str(interval_minutes),))
            self.db.execute("UPDATE preferences SET value=? WHERE key='scheduler_enabled'", (json.dumps(bool(scheduler_enabled)),))
            self.db.commit()
        return self.get_settings()

    def unverified_articles(self, source_id):
        with self._lock:
            return [dict(r) for r in self.db.execute('SELECT url,title FROM notices WHERE source_id=? AND is_demo=0 AND date_verified=0 ORDER BY published_at DESC', (source_id,))]

    def get_coverage(self, site_id):
        with self._lock:
            row = self.db.execute('SELECT report FROM site_coverage WHERE site_id=?', (site_id,)).fetchone()
            return json.loads(row['report']) if row else {'pages': [], 'pending': []}

    def save_coverage(self, site_id, report):
        report['updated_at'] = _now()
        with self._lock:
            self.db.execute('INSERT INTO site_coverage(site_id,report) VALUES(?,?) ON CONFLICT(site_id) DO UPDATE SET report=excluded.report',
                            (site_id, json.dumps(report, ensure_ascii=False)))
            self.db.commit()

    def add_notice_section(self, notice_id, url, label):
        with self._lock:
            self.db.execute('INSERT OR REPLACE INTO notice_sections(notice_id,url,label) VALUES(?,?,?)', (notice_id,url,label))
            self.db.commit()

    def update_site_result(self, site_id, status, error, new_count=0):
        with self._lock:
            self.db.execute("UPDATE sites SET status=?,error=?,last_checked=?,new_count=? WHERE id=?", (status,error,_now(),new_count,site_id)); self.db.commit()

    def set_crawl_state(self, running, last_finished=None, progress=None):
        with self._lock:
            self.db.execute("UPDATE crawl_state SET running=?,last_finished=COALESCE(?,last_finished),progress=? WHERE singleton=1",
                            (int(running),last_finished,json.dumps(progress or {}, ensure_ascii=False))); self.db.commit()

    def try_claim_crawl(self, site_id=None):
        with self._lock:
            try:
                self.db.execute("BEGIN IMMEDIATE")
                cur = self.db.execute("UPDATE crawl_state SET running=1,progress=? WHERE singleton=1 AND running=0", (json.dumps({"site_id":site_id}),))
                self.db.commit()
                if cur.rowcount == 1: self.crawl_cancel.clear()
                return cur.rowcount == 1
            except Exception:
                self.db.rollback()
                raise

    def prepare_restart(self):
        with self._lock:
            state = self.get_crawl_state()
            if state['running'] and not self.crawl_cancel.is_set():
                self.db.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES('resume_crawl',?)", (json.dumps({'site_id':state.get('site_id')}),))
                self.db.commit()
            self.crawl_cancel.set()

    def health(self):
        with self._lock:
            self.db.execute('SELECT 1').fetchone()
        return {'database': 'ok'}

    def get_crawl_state(self):
        with self._lock: row = self.db.execute("SELECT * FROM crawl_state WHERE singleton=1").fetchone()
        return {"running": bool(row["running"]), "last_finished": row["last_finished"], **json.loads(row["progress"])}

    def stats(self, mode="demo"):
        notices = self.list_notices(mode=mode)["items"]
        today = (DEMO_TODAY if mode == "demo" else date.today()).isoformat()
        with self._lock:
            connected = self.db.execute("SELECT COUNT(*) FROM sites WHERE status='正常'").fetchone()[0]
            errors = self.db.execute("SELECT COUNT(*) FROM sites WHERE status IN ('延迟','失败')").fetchone()[0]
        trend = []
        base = DEMO_TODAY if mode == "demo" else date.today()
        for offset in range(6, -1, -1):
            day = (base - timedelta(days=offset)).isoformat()
            trend.append({"date": day, "count": sum(n["published_at"][:10] == day for n in notices)})
        window_start = (base - timedelta(days=6)).isoformat()
        recent = [n for n in notices if window_start <= n["published_at"][:10] <= base.isoformat()]
        def counts(items, key):
            result = {}
            for n in items: result[n[key]] = result.get(n[key], 0) + 1
            return [{"name": k, "count": v} for k,v in sorted(result.items(), key=lambda x:(-x[1],x[0]))]
        subs = self.get_subscriptions()
        messages = self.list_messages(mode)["items"]
        terminal = [m for m in messages if m["status"] in ("已送达", "失败")]
        delivered = sum(m["status"] == "已送达" for m in terminal)
        return {"directory_count":len(self.list_sites()),"connected_count":connected,
                "today_count":sum(n["published_at"][:10] == today for n in notices),"error_count":errors,
                "subscriber_count":int(bool(subs["sources"] or subs["keywords"] or subs["categories"])),
                "push_rate":round(100 * delivered / len(terminal), 1) if terminal else None,
                "trend":trend,"activity":counts(recent,"source_name"),"categories":counts(notices,"category"),
                "last_updated":_now(),"mode":mode}
