import json, os, socket, subprocess, sys, tempfile, time, unittest, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class ProcessRecoveryTest(unittest.TestCase):
 @unittest.skipUnless(os.name == 'posix', 'requires graceful POSIX SIGTERM; Windows terminate uses TerminateProcess')
 def test_sigterm_and_restart_resume_same_site(self):
  try:
   with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
  except PermissionError:self.skipTest('sandbox blocks loopback binding')
  opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
  def request(path,body=None):
   req=urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','Origin':'http://127.0.0.1:5173'})
   with opener.open(req,timeout=2) as r:return json.load(r)
  def until(check):
   for _ in range(100):
    try:
     value=check()
     if value:return value
    except OSError:pass
    time.sleep(.05)
   self.fail('local server condition timed out')
  fixture="""
import sys,time
from backend import collector,server
def collect(store,site):
 store.save_coverage(site['id'],{'pages':[],'pending':[{'url':site['url'],'label':'fixture'}],'round_pages':1})
 while not store.crawl_cancel.is_set():time.sleep(.03)
 return 0
collector.collect_site=collect
server.main()
"""
  with tempfile.TemporaryDirectory() as tmp:
   args=[sys.executable,'-c',fixture,'--port',str(port),'--db',str(Path(tmp)/'test.db')]
   process=None
   try:
    process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={**os.environ,'SWU_NETWORK_MODE':'direct'})
    until(lambda:request('health')['ok']);request('crawl',{'site_id':13});until(lambda:request('crawl').get('site_id')==13)
    process.terminate();self.assertEqual(0,process.wait(timeout=8))
    process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={**os.environ,'SWU_NETWORK_MODE':'direct'})
    until(lambda:request('crawl').get('running') and request('crawl').get('site_id')==13)
    self.assertEqual('ok',request('health')['database'])
    request('crawl/stop',{});until(lambda:not request('crawl')['running'])
   finally:
    if process and process.poll() is None:process.terminate();process.wait(timeout=8)
