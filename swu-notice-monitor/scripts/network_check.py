#!/usr/bin/env python3
"""Read-only deployment preflight. Never prints proxy credentials."""
import argparse
import json
from pathlib import Path
import socket
import sys
import urllib.parse
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.collector import network_proxies,network_summary,validate_fetch_url,SafeRedirect,fetch_html
parser=argparse.ArgumentParser(description='检查采集网络；不修改数据库')
parser.add_argument('--fetch',action='store_true',help='实际读取三个公开网站首页')
args=parser.parse_args()
report={'network':network_summary(),'sites':[]}
proxies=network_proxies()
for url in ['https://dzb.swu.edu.cn/','https://cis.swu.edu.cn/','https://xsc.swu.edu.cn/']:
 item={'url':url};host=urllib.parse.urlsplit(url).hostname
 try:
  item['addresses']=sorted({x[4][0] for x in socket.getaddrinfo(host,443)})
  validate_fetch_url(url,proxies)
  if args.fetch:
   opener=urllib.request.build_opener(urllib.request.ProxyHandler(proxies),SafeRedirect(host,proxies));opener.swu_proxies=proxies
   html,final=fetch_html(opener,url,'SWUNoticeMonitor/1.0',1500000);item['html_characters']=len(html)
  item['ok']=True
 except Exception as exc:item.update(ok=False,error=str(exc))
 report['sites'].append(item)
print(json.dumps(report,ensure_ascii=False,indent=2))
sys.exit(0 if all(x['ok'] for x in report['sites']) else 1)
