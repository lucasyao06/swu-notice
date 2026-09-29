import argparse
import os
import signal
import json
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

if __package__:
    from .collector import start_collection, validate_list_url, network_summary
    from .store import Store
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from backend.collector import start_collection, validate_list_url, network_summary
    from backend.store import Store


ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"} | {x.strip() for x in os.environ.get("SWU_ALLOWED_ORIGINS", "").split(",") if x.strip()}


def origin_allowed(origin):
    return origin is None or origin in ALLOWED_ORIGINS


def parse_content_length(value):
    size = int(value)
    if size < 0:
        raise ValueError("Content-Length 不能为负数")
    if size > 100_000:
        raise ValueError("请求体过大")
    return size


def _bool(value, name):
    if type(value) is not bool:
        raise ValueError(f"{name} 必须是布尔值")
    return value


class APIHandler(BaseHTTPRequestHandler):
    server_version = "SWUNoticeMonitor/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.log_date_time_string(), fmt % args))

    def _send(self, status, payload):
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(raw)))
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        try:
            size = parse_content_length(self.headers.get("Content-Length", "0"))
            value = json.loads(self.rfile.read(size) or b"{}")
            if not isinstance(value, dict): raise ValueError("请求体必须是 JSON 对象")
            return value
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"无效 JSON: {exc}") from exc

    def _parsed(self):
        return urllib.parse.urlparse(self.path)

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if origin not in ALLOWED_ORIGINS:
            return self._send(403, {"error": "不允许的来源"})
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, PATCH, PUT, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Vary", "Origin")
        self.end_headers()

    def do_GET(self):
        try: self._get()
        except ValueError as exc: self._send(400, {"error": str(exc)})
        except Exception as exc: self._send(500, {"error": str(exc)})

    def _get(self):
        parsed = self._parsed(); path = parsed.path; query = urllib.parse.parse_qs(parsed.query)
        one = lambda key, default="": query.get(key, [default])[0]
        if path == "/api/health":
            return self._send(200, {"ok": True, **self.server.store.health(), 'network': network_summary(), 'crawl': self.server.store.get_crawl_state()})
        if path == "/api/sites":
            items = self.server.store.list_sites(); return self._send(200, {"items": items, "total": len(items)})
        if path.startswith('/api/sites/') and path.endswith('/coverage'):
            site_id = int(path.split('/')[3])
            if not self.server.store.get_site(site_id):
                return self._send(404, {'error': '网站不存在'})
            return self._send(200, self.server.store.get_coverage(site_id))
        if path == "/api/notices":
            mode = one("mode", "demo")
            if mode not in ("demo", "live"): raise ValueError("mode 必须是 demo 或 live")
            read = one("read", "all"); period = one("period", "all")
            if read not in ("all","unread","read","favorite"): raise ValueError("无效 read 参数")
            if period not in ("all","today","week","month","custom"): raise ValueError("无效 period 参数")
            return self._send(200, self.server.store.list_notices(mode=mode,q=one("q"),type=one("type"),
                category=one("category"),read=read,source=one("source"),period=period,start=one("start"),
                end=one("end"),subscribed=one("subscribed","0") == "1",
                limit=int(one("limit")) if one("limit") else None,offset=int(one("offset","0"))))
        if path.startswith('/api/notices/'):
            item = self.server.store.get_notice(int(path.rsplit('/',1)[1]))
            return self._send(200,item) if item else self._send(404,{'error':'通知不存在'})
        if path == "/api/subscriptions": return self._send(200, self.server.store.get_subscriptions())
        if path in ("/api/messages", "/api/stats"):
            mode = one("mode", "demo")
            if mode not in ("demo", "live"): raise ValueError("mode 必须是 demo 或 live")
            if path == "/api/messages": return self._send(200, self.server.store.list_messages(mode))
            return self._send(200, self.server.store.stats(mode))
        if path == "/api/settings": return self._send(200, self.server.store.get_settings())
        if path == "/api/crawl": return self._send(200, self.server.store.get_crawl_state())
        self._send(404, {"error": "接口不存在"})

    def _mutate(self, method):
        if not origin_allowed(self.headers.get("Origin")): return self._send(403, {"error": "不允许的来源"})
        path = self._parsed().path
        body = self._body()
        if method == 'POST' and path == '/api/crawl/stop':
            self.server.store.crawl_cancel.set()
            return self._send(200, {'ok': True, 'stopping': True})
        if method == "PATCH" and path == "/api/sites":
            if set(body) != {"enabled"}: raise ValueError("批量设置只接受 enabled")
            enabled = _bool(body["enabled"], "enabled")
            items = self.server.store.set_all_sites_enabled(enabled)
            return self._send(200, {"items": items, "total": len(items),
                "enabled_count": sum(x["enabled"] for x in items)})
        if method == "PATCH" and path.startswith("/api/sites/"):
            site_id = int(path.rsplit("/",1)[1]); site = self.server.store.get_site(site_id)
            if not site: return self._send(404,{"error":"站点不存在"})
            if set(body) != {"enabled","list_url"}: raise ValueError("需要 enabled 和 list_url")
            _bool(body["enabled"], "enabled")
            if not isinstance(body["list_url"], str): raise ValueError("list_url 必须是字符串")
            if body["list_url"]: validate_list_url(site["url"], body["list_url"])
            return self._send(200, self.server.store.update_site(site_id, body["enabled"], body["list_url"]))
        if method == "PATCH" and path.startswith("/api/notices/"):
            notice_id = int(path.rsplit("/",1)[1])
            if not body or not set(body) <= {"read","favorite"}: raise ValueError("只支持 read 和 favorite")
            for key in body: _bool(body[key], key)
            item = self.server.store.update_notice(notice_id, **body)
            return self._send(200,item) if item else self._send(404,{"error":"通知不存在"})
        if method == "PUT" and path == "/api/subscriptions":
            if set(body) != {"sources","keywords","categories","in_app"}: raise ValueError("订阅字段不完整")
            if not all(isinstance(body[k],list) for k in ("sources","keywords","categories")): raise ValueError("订阅项必须是数组")
            _bool(body["in_app"],"in_app")
            return self._send(200,self.server.store.save_subscriptions(body["sources"],body["keywords"],body["categories"],body["in_app"]))
        if method == "PATCH" and path.startswith("/api/messages/"):
            if body != {"read": True}: raise ValueError("消息只支持标记已读")
            return self._send(200,{"ok":True}) if self.server.store.read_message(int(path.rsplit('/',1)[1])) else self._send(404,{"error":"消息不存在"})
        if method == "PUT" and path == "/api/settings":
            if set(body) != {"interval_minutes","scheduler_enabled"}: raise ValueError("设置字段不完整")
            interval = body["interval_minutes"]
            if type(interval) is not int or not 5 <= interval <= 1440: raise ValueError("interval_minutes 必须在 5 到 1440 之间")
            _bool(body["scheduler_enabled"],"scheduler_enabled")
            return self._send(200,self.server.store.save_settings(interval,body["scheduler_enabled"]))
        if method == "POST" and path == "/api/crawl":
            if set(body) - {"site_id"}: raise ValueError("只支持 site_id")
            site_id = body.get("site_id")
            if site_id is not None and type(site_id) is not int: raise ValueError("site_id 必须是整数")
            if site_id is not None and not self.server.store.get_site(site_id): return self._send(404,{"error":"站点不存在"})
            if not start_collection(self.server.store,site_id): return self._send(409,{"error":"采集任务正在运行"})
            return self._send(200,{"ok":True,"running":True})
        self._send(404,{"error":"接口不存在"})

    def do_PATCH(self):
        try: self._mutate("PATCH")
        except (ValueError,KeyError) as exc: self._send(400,{"error":str(exc)})
        except Exception as exc: self._send(500,{"error":str(exc)})
    def do_PUT(self):
        try: self._mutate("PUT")
        except (ValueError,KeyError) as exc: self._send(400,{"error":str(exc)})
        except Exception as exc: self._send(500,{"error":str(exc)})
    def do_POST(self):
        try: self._mutate("POST")
        except (ValueError,KeyError) as exc: self._send(400,{"error":str(exc)})
        except Exception as exc: self._send(500,{"error":str(exc)})


class MonitorServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address, store):
        self.store = store
        super().__init__(address, APIHandler)


def scheduler_loop(store, stop):
    next_run = time.monotonic()
    while not stop.wait(5):
        settings = store.get_settings()
        if settings["scheduler_enabled"] and time.monotonic() >= next_run:
            if start_collection(store):
                next_run = time.monotonic() + settings["interval_minutes"] * 60
        elif not settings["scheduler_enabled"]:
            next_run = time.monotonic()


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="SWU Notice Monitor API")
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--host",default=os.environ.get("SWU_BIND_HOST","127.0.0.1"))
    parser.add_argument("--db",type=Path,default=root / "data" / "monitor.sqlite3")
    args = parser.parse_args()
    store = Store(args.db, root / "data" / "sites.json")
    server = MonitorServer((args.host,args.port),store)
    stop = threading.Event(); threading.Thread(target=scheduler_loop,args=(store,stop),daemon=True).start()
    network_summary()  # Fail fast on invalid deployment configuration.
    def terminate(*_):
        store.prepare_restart(); stop.set()
        threading.Thread(target=server.shutdown, daemon=True).start()
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    if store.resume_requested:
        start_collection(store, store.resume_site_id)
        print('已恢复上次中断的采集任务', flush=True)
    print(f"API listening on http://{args.host}:{args.port}")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally:
        stop.set(); store.prepare_restart(); server.server_close()
        if store.crawl_thread: store.crawl_thread.join(timeout=50)
        if not store.crawl_thread or not store.crawl_thread.is_alive(): store.close()


if __name__ == "__main__": main()
