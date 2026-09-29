import socket, unittest, urllib.error
from unittest.mock import patch
from backend import collector as c
class NetworkResilienceTests(unittest.TestCase):
 def test_benchmark_ipv6_with_registered_https_proxy(self):
  dns=[(socket.AF_INET6,1,6,'',('2001:2::2e',443,0,0))]
  with patch('socket.getaddrinfo',return_value=dns),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}),patch('urllib.request.proxy_bypass',return_value=False):c.validate_fetch_url('https://dzb.swu.edu.cn/')
 def test_transient_fetch_retry_then_success(self):
  with patch.object(c,'_fetch_html_once',side_effect=[urllib.error.URLError(TimeoutError('timeout')),('ok','https://dzb.swu.edu.cn/')]) as fetch,patch.object(c.time,'sleep'):
   self.assertEqual(('ok','https://dzb.swu.edu.cn/'),c.fetch_html(None,'https://dzb.swu.edu.cn/','test',1024));self.assertEqual(2,fetch.call_count)
 def test_no_retry_for_permanent_http_or_blocked_target(self):
  for error in [urllib.error.HTTPError('https://dzb.swu.edu.cn',403,'denied',{},None),ValueError('blocked')]:
   with patch.object(c,'_fetch_html_once',side_effect=error) as fetch,patch.object(c.time,'sleep'):
    with self.assertRaises(type(error)):c.fetch_html(None,'https://dzb.swu.edu.cn/','test',1024)
    self.assertEqual(1,fetch.call_count)
   if isinstance(error,urllib.error.HTTPError):error.close()
 def test_direct_mode_ignores_system_proxy(self):
  with patch.dict('os.environ',{'SWU_NETWORK_MODE':'direct'}),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}):self.assertEqual({},c.network_proxies())
 def test_explicit_proxy_mode_requires_config(self):
  with patch.dict('os.environ',{'SWU_NETWORK_MODE':'proxy','SWU_HTTPS_PROXY':''}):
   with self.assertRaisesRegex(ValueError,'SWU_HTTPS_PROXY'):c.network_proxies()

 def test_tls_disconnect_is_retried_but_certificate_errors_are_not(self):
  import ssl
  with patch.object(c,'_fetch_html_once',side_effect=[urllib.error.URLError(ssl.SSLEOFError('connection closed')),('ok','https://dzb.swu.edu.cn/')]) as call,patch.object(c.time,'sleep'):
   c.fetch_html(None,'https://dzb.swu.edu.cn/','test',1000);self.assertEqual(2,call.call_count)
  with patch.object(c,'_fetch_html_once',side_effect=urllib.error.URLError(ssl.SSLCertVerificationError('bad certificate'))) as call,patch.object(c.time,'sleep'):
   with self.assertRaises(urllib.error.URLError):c.fetch_html(None,'https://dzb.swu.edu.cn/','test',1000)
   self.assertEqual(1,call.call_count)

class RestartTests(unittest.TestCase):
 def test_restart_recovers_exact_interrupted_site_and_keeps_queue(self):
  import tempfile
  from pathlib import Path
  from backend.store import Store
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'test.db';directory=Path(__file__).resolve().parents[1]/'data/sites.json'
   s=Store(path,directory);s.try_claim_crawl(13)
   s.save_coverage(13,{'pages':[],'pending':[{'url':'https://xsc.swu.edu.cn/list.htm','label':'通知'}]})
   s.prepare_restart();s.set_crawl_state(False,progress={'stopped':True});s.close()
   s=Store(path,directory)
   try:self.assertTrue(s.resume_requested);self.assertEqual(13,s.resume_site_id);self.assertEqual(1,len(s.get_coverage(13)['pending']))
   finally:s.close()
 def test_user_stopped_crawl_does_not_restart(self):
  import tempfile
  from pathlib import Path
  from backend.store import Store
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'test.db';directory=Path(__file__).resolve().parents[1]/'data/sites.json'
   s=Store(path,directory);s.try_claim_crawl(13);s.crawl_cancel.set();s.set_crawl_state(False,progress={'stopped':True});s.prepare_restart();s.close()
   s=Store(path,directory)
   try:self.assertFalse(s.resume_requested)
   finally:s.close()
