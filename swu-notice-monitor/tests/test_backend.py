import json
import http.client
import urllib.error
import tempfile
import threading
import unittest
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class StoreTests(unittest.TestCase):
    def setUp(self):
        from backend.store import Store

        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "monitor.sqlite3", ROOT / "data" / "sites.json")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_imports_real_directory_once(self):
        sites = self.store.list_sites()
        self.assertEqual(89, len(sites))
        self.assertEqual("本科生院（招生办公室、教学质量监控与评估中心、教师教学发展中心）", sites[10]["name"])
        self.store.import_sites(ROOT / "data" / "sites.json")
        self.assertEqual(89, len(self.store.list_sites()))

    def test_demo_filtering_uses_reference_date_and_combined_filters(self):
        result = self.store.list_notices(
            mode="demo", q="课程", source="11", category="教学教务", period="today"
        )
        self.assertEqual(1, result["total"])
        self.assertEqual("关于本学期课程补退选安排的通知", result["items"][0]["title"])
        self.assertTrue(result["items"][0]["is_demo"])
        self.assertEqual(0, self.store.list_notices(mode="demo", q="不存在的通知")["total"])

    def test_demo_dates_categories_and_custom_end_are_exact(self):
        items = self.store.list_notices(mode="demo")["items"]
        expected = {
            "关于本学期课程补退选安排的通知": ("2026-09-22 10:20", "教学教务"),
            "人工智能与软件工程学术交流活动": ("2026-09-22 09:40", "学术讲座"),
            "研究生培养相关材料提交提醒": ("2026-09-21 16:30", "教学教务"),
            "自习空间开放与预约服务说明": ("2026-09-21 14:00", "校园服务"),
            "学生国际交流项目说明会": ("2026-09-20 15:30", "国际交流"),
        }
        self.assertEqual(expected, {x["title"]: (x["published_at"], x["category"]) for x in items})
        custom = self.store.list_notices(mode="demo", period="custom", start="2026-09-21", end="2026-09-21")
        self.assertEqual(2, custom["total"])
        self.assertEqual(2, self.store.stats("demo")["today_count"])

    def test_initial_subscriptions_are_created_only_once(self):
        expected = {
            "sources": [11, 28, 67],
            "keywords": ["人工智能", "课程补退选"],
            "categories": ["国际交流", "教学教务"],
            "in_app": True,
        }
        self.assertEqual(expected, self.store.get_subscriptions())
        self.store.save_subscriptions([], [], [], False)
        self.store.close()
        from backend.store import Store
        self.store = Store(Path(self.tmp.name) / "monitor.sqlite3", ROOT / "data" / "sites.json")
        self.assertEqual({"sources": [], "keywords": [], "categories": [], "in_app": False}, self.store.get_subscriptions())

    def test_subscription_save_normalizes_duplicates_and_is_atomic_on_invalid_input(self):
        saved = self.store.save_subscriptions([11, 11], [" 通知 ", "通知"], ["教学教务", "教学教务"], True)
        self.assertEqual([11], saved["sources"])
        self.assertEqual(["通知"], saved["keywords"])
        self.assertEqual(["教学教务"], saved["categories"])
        before = self.store.get_subscriptions()
        for args in [
            ([9999], [], [], True),
            ([], [""], [], True),
            ([], [], ["不存在"], True),
            ([], [123], [], True),
        ]:
            with self.assertRaises(ValueError):
                self.store.save_subscriptions(*args)
            self.assertEqual(before, self.store.get_subscriptions())

    def test_stale_running_state_is_cleared_on_restart(self):
        self.store.set_crawl_state(True, progress={"completed": 1, "total": 2})
        self.store.close()
        from backend.store import Store
        self.store = Store(Path(self.tmp.name) / "monitor.sqlite3", ROOT / "data" / "sites.json")
        self.assertFalse(self.store.get_crawl_state()["running"])

    def test_crawl_claim_is_atomic(self):
        results = []
        barrier = threading.Barrier(6)

        def claim():
            barrier.wait()
            results.append(self.store.try_claim_crawl())

        threads = [threading.Thread(target=claim) for _ in range(6)]
        for thread in threads: thread.start()
        for thread in threads: thread.join()
        self.assertEqual(1, results.count(True))
        self.assertEqual(5, results.count(False))

    def test_stats_use_local_subscriber_and_terminal_delivery_semantics(self):
        stats = self.store.stats("demo")
        self.assertEqual(1, stats["subscriber_count"])
        self.assertEqual(50.0, stats["push_rate"])
        self.store.save_subscriptions([], [], [], True)
        self.assertEqual(0, self.store.stats("demo")["subscriber_count"])
        self.assertIsNone(self.store.stats("live")["push_rate"])

    def test_error_count_includes_delayed_and_failed_sites(self):
        self.store.update_site_result(1, "延迟", "timeout")
        self.store.update_site_result(2, "失败", "parser")
        self.store.update_site_result(3, "正常", None)
        self.assertEqual(2, self.store.stats("demo")["error_count"])

    def test_activity_only_includes_notices_from_trend_window(self):
        today = date.today()
        self.store.upsert_live_notice(11, "本周通知", today.isoformat(), "教学教务", "", "https://ugs.swu.edu.cn/current.htm")
        self.store.upsert_live_notice(12, "旧通知", (today - timedelta(days=8)).isoformat(), "教学教务", "", "https://yjsyygb.swu.edu.cn/old.htm")
        activity = self.store.stats("live")["activity"]
        self.assertEqual(["本科生院（招生办公室、教学质量监控与评估中心、教师教学发展中心）"], [x["name"] for x in activity])

    def test_read_favorite_and_settings_persist_across_store_instances(self):
        notice_id = self.store.list_notices(mode="demo")["items"][0]["id"]
        self.store.update_notice(notice_id, read=True, favorite=True)
        self.store.save_settings(15, True)
        self.store.close()

        from backend.store import Store

        self.store = Store(Path(self.tmp.name) / "monitor.sqlite3", ROOT / "data" / "sites.json")
        item = self.store.get_notice(notice_id)
        self.assertTrue(item["read"])
        self.assertTrue(item["favorite"])
        self.assertEqual({"interval_minutes": 15, "scheduler_enabled": True}, self.store.get_settings())

    def test_live_notice_deduplicates_by_source_and_url(self):
        payload = dict(
            source_id=11,
            title="真实采集通知",
            published_at="2026-09-22",
            category="教学教务",
            summary="摘要",
            url="https://ugs.swu.edu.cn/info/1.htm",
        )
        first, inserted_first = self.store.upsert_live_notice(**payload)
        second, inserted_second = self.store.upsert_live_notice(**payload)
        self.assertTrue(inserted_first)
        self.assertFalse(inserted_second)
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(1, self.store.list_notices(mode="live")["total"])

    def test_live_subscription_delivery_creates_one_persistent_message(self):
        self.store.save_subscriptions([11], ["补退选"], ["教学教务"], True)
        notice, inserted = self.store.upsert_live_notice(
            source_id=11,
            title="补退选安排更新",
            published_at="2026-09-22",
            category="教学教务",
            summary="",
            url="https://ugs.swu.edu.cn/info/2.htm",
        )
        self.assertTrue(inserted)
        messages = self.store.list_messages("live")
        self.assertEqual(1, messages["unread"])
        self.assertEqual(notice["id"], messages["items"][0]["notice_id"])
        self.store.upsert_live_notice(
            source_id=11, title="补退选安排更新", published_at="2026-09-22",
            category="教学教务", summary="", url="https://ugs.swu.edu.cn/info/2.htm"
        )
        self.assertEqual(1, len(self.store.list_messages("live")["items"]))

    def test_demo_messages_are_present_and_clearly_labeled(self):
        messages = self.store.list_messages("demo")
        self.assertEqual({"已送达", "待发送", "失败"}, {item["status"] for item in messages["items"]})
        self.assertTrue(all(item["is_demo"] for item in messages["items"]))


class ApiSecurityTests(unittest.TestCase):
    def test_mutation_origin_policy(self):
        from backend.server import origin_allowed, parse_content_length

        self.assertTrue(origin_allowed(None))
        self.assertTrue(origin_allowed("http://127.0.0.1:5173"))
        self.assertTrue(origin_allowed("http://localhost:5173"))
        self.assertFalse(origin_allowed("http://evil.example"))
        self.assertFalse(origin_allowed("null"))
        with self.assertRaises(ValueError):
            parse_content_length("-1")

    def test_http_contract_and_origin_rejection(self):
        from backend.server import MonitorServer
        from backend.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "api.sqlite3", ROOT / "data" / "sites.json")
            try:
                server = MonitorServer(("127.0.0.1", 0), store)
            except PermissionError:
                store.close()
                self.skipTest("sandbox blocks loopback socket binding")
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                conn = http.client.HTTPConnection("127.0.0.1", server.server_port)
                conn.request("GET", "/api/sites")
                response = conn.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(200, response.status)
                self.assertEqual(89, payload["total"])

                body = json.dumps({"interval_minutes": 60, "scheduler_enabled": False})
                conn.request("PUT", "/api/settings", body, {
                    "Content-Type": "application/json", "Origin": "http://evil.example"
                })
                response = conn.getresponse()
                self.assertEqual(403, response.status)
                self.assertIn("error", json.loads(response.read()))
            finally:
                server.shutdown()
                server.server_close()
                store.close()


class CollectorTests(unittest.TestCase):
    def test_failure_status_distinguishes_timeout(self):
        from backend.collector import crawl_failure_status

        self.assertEqual("延迟", crawl_failure_status(TimeoutError("timed out")))
        self.assertEqual("失败", crawl_failure_status(ValueError("parser limitation")))

    def test_robots_fetch_uses_bounded_safe_opener(self):
        from backend.collector import read_robots

        class Response(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): self.close()

        class Opener:
            def __init__(self): self.calls = []
            def open(self, request, timeout):
                self.calls.append((request.full_url, timeout))
                return Response(b"User-agent: *\nDisallow: /private\n")

        opener = Opener()
        robots = read_robots(opener, "https://example.edu/robots.txt", max_bytes=128)
        self.assertEqual([("https://example.edu/robots.txt", 15)], opener.calls)
        self.assertFalse(robots.can_fetch("SWUNoticeMonitor/1.0", "https://example.edu/private/a"))

        class OversizedOpener(Opener):
            def open(self, request, timeout): return Response(b"x" * 130)

        with self.assertRaises(ValueError):
            read_robots(OversizedOpener(), "https://example.edu/robots.txt", max_bytes=128)

    def test_extracts_anchor_with_sibling_date_from_list_and_table(self):
        from backend.collector import extract_notices

        html = """
        <ul>
          <li><span>2026-09-22</span><a href="/info/1001/2002.htm">课程安排通知</a></li>
          <li><a href="/content/88.html">学术活动预告</a><span>2026年9月21日</span></li>
        </ul>
        <table><tr><td><a href="/info/9.htm">图书馆服务说明</a></td><td>2026/09/20</td></tr></table>
        """
        self.assertEqual([
            ("课程安排通知", "2026-09-22", "https://ugs.swu.edu.cn/info/1001/2002.htm"),
            ("学术活动预告", "2026-09-21", "https://ugs.swu.edu.cn/content/88.html"),
            ("图书馆服务说明", "2026-09-20", "https://ugs.swu.edu.cn/info/9.htm"),
        ], extract_notices(html, "https://ugs.swu.edu.cn/list.htm"))

    def test_extractor_rejects_invalid_dates_and_deduplicates_navigation(self):
        from backend.collector import extract_notices

        html = """
        <li><span>2026-02-30</span><a href="/info/bad.htm">无效日期通知</a></li>
        <li><span>2026-09-22</span><a href="/index.htm">首页</a><a href="/info/1.htm">有效通知标题</a></li>
        <tr><td>2026-09-22</td><td><a href="/info/1.htm">有效通知标题</a></td></tr>
        """
        self.assertEqual([
            ("有效通知标题", "2026-09-22", "https://ugs.swu.edu.cn/info/1.htm")
        ], extract_notices(html, "https://ugs.swu.edu.cn/list.htm"))

    def test_robots_404_allows_and_403_disallows(self):
        from backend.collector import read_robots

        class ErrorOpener:
            def __init__(self, status): self.status = status
            def open(self, request, timeout):
                raise urllib.error.HTTPError(request.full_url, self.status, "status", {}, None)

        missing = read_robots(ErrorOpener(404), "https://example.edu/robots.txt")
        self.assertTrue(missing.can_fetch("SWUNoticeMonitor/1.0", "https://example.edu/info/1.htm"))
        forbidden = read_robots(ErrorOpener(403), "https://example.edu/robots.txt")
        self.assertFalse(forbidden.can_fetch("SWUNoticeMonitor/1.0", "https://example.edu/info/1.htm"))


if __name__ == "__main__":
    unittest.main()
