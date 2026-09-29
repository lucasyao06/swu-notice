import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from backend.store import Store
ROOT=Path(__file__).resolve().parents[1]

class BulkCollectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(Path(self.tmp.name)/'test.sqlite3',ROOT/'data/sites.json')
 def tearDown(self):self.store.close();self.tmp.cleanup()
 def test_bulk_enable_preserves_custom_urls_and_status(self):
  self.store.update_site(28,False,'https://foreign.swu.edu.cn/index/tzgg.htm')
  self.store.update_site_result(28,'正常',None,15)
  self.store.set_all_sites_enabled(True)
  self.assertEqual(89,sum(s['enabled'] for s in self.store.list_sites()))
  self.assertEqual('https://foreign.swu.edu.cn/index/tzgg.htm',self.store.get_site(28)['list_url'])
  self.assertEqual('正常',self.store.get_site(28)['status'])
  self.store.set_all_sites_enabled(False)
  self.assertEqual(0,sum(s['enabled'] for s in self.store.list_sites()))
 def test_notice_discovery_prefers_same_host_list_not_notice_detail(self):
  from backend.collector import discover_notice_lists
  html='<a href="index/tzgg.htm">通知公告</a><a href="info/1.htm">开学通知</a><a href="https://evil.example/tzgg.htm">通知公告</a><a href="index/tzgg.htm">通知公告</a>'
  self.assertEqual(['https://foreign.swu.edu.cn/index/tzgg.htm'],discover_notice_lists(html,'https://foreign.swu.edu.cn/'))
 def test_bulk_collection_finishes_with_per_site_results(self):
  from backend.collector import run_collection
  for id in [1,28]:self.store.update_site(id,True,'')
  def collect(store,site):
   if site['id']==1:raise TimeoutError('test timeout')
   return 3
  with patch('backend.collector.collect_site',side_effect=collect):run_collection(self.store)
  self.assertFalse(self.store.get_crawl_state()['running'])
  self.assertEqual(2,self.store.get_crawl_state()['completed'])
  self.assertEqual('延迟',self.store.get_site(1)['status'])
  self.assertEqual('正常',self.store.get_site(28)['status'])

class BulkApiTests(unittest.TestCase):
 def test_bulk_endpoint_updates_all_sites_and_disables_response_caching(self):
  import threading,urllib.request
  from backend.server import MonitorServer
  with tempfile.TemporaryDirectory() as tmp:
   store=Store(Path(tmp)/'test.sqlite3',ROOT/'data/sites.json')
   try:server=MonitorServer(('127.0.0.1',0),store)
   except PermissionError:
    store.close();self.skipTest('sandbox blocks loopback socket binding')
   thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
   opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
   try:
    req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}/api/sites',data=b'{"enabled":true}',method='PATCH',headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:5173'})
    with opener.open(req,timeout=3) as r:
     self.assertEqual('no-store',r.headers['Cache-Control']);data=json.load(r)
    self.assertEqual(89,data['enabled_count'])
    self.assertTrue(all(s['enabled'] for s in data['items']))
   finally:server.shutdown();server.server_close();store.close()
