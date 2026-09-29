import socket
import unittest
from unittest.mock import patch
from backend.collector import validate_list_url, _resolved_public, extract_notices, SafeRedirect
import urllib.request

FAKE = [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('198.18.0.110',443)),(socket.AF_INET6,socket.SOCK_STREAM,6,'',('fdfe:dcba:9876::6c',443,0,0))]

class LiveCollectionRegressionTests(unittest.TestCase):
    def test_save_configuration_does_not_require_live_dns(self):
        with patch('socket.getaddrinfo',side_effect=socket.gaierror('offline')):
            self.assertEqual('https://dzb.swu.edu.cn/',validate_list_url('https://dzb.swu.edu.cn/','https://dzb.swu.edu.cn/'))

    def test_registered_https_supports_configured_proxy_fake_dns(self):
        from backend.collector import validate_fetch_url
        with patch('socket.getaddrinfo',return_value=FAKE),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}):
            validate_fetch_url('https://dzb.swu.edu.cn/')
            for url in ['https://unknown.example/','http://dzb.swu.edu.cn/']:
                with self.assertRaises(ValueError):validate_fetch_url(url)

    def test_private_targets_stay_blocked_and_nonstandard_ports_rejected(self):
        from backend.collector import validate_fetch_url
        for ip in ['127.0.0.1','10.0.0.1','192.168.1.1','169.254.169.254','::1']:
            with patch('socket.getaddrinfo',return_value=[(socket.AF_INET,1,6,'',(ip,443))]),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}):
                with self.assertRaises(ValueError):validate_fetch_url('https://dzb.swu.edu.cn/')
        for url in ['https://user:pass@dzb.swu.edu.cn/','https://dzb.swu.edu.cn:8080/','https://127.0.0.1/','https://dzb.swu.edu.cn.evil.example/']:
            with self.assertRaises(ValueError):validate_list_url('https://dzb.swu.edu.cn/',url)

    def test_split_official_year_and_month_day_are_not_discarded(self):
        html='<li><div class="date"><div class="day">09-18</div><div class="year">[2026]</div></div><a href="info/1004/3707.htm">学校党委常委会召开会议</a></li>'
        self.assertEqual([('学校党委常委会召开会议','2026-09-18','https://dzb.swu.edu.cn/info/1004/3707.htm')],extract_notices(html,'https://dzb.swu.edu.cn/'))

    def test_fake_ip_exception_does_not_apply_to_proxy_bypass(self):
        from backend.collector import validate_fetch_url
        with patch('socket.getaddrinfo',return_value=FAKE),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}),patch('urllib.request.proxy_bypass',return_value=True):
            with self.assertRaises(ValueError):validate_fetch_url('https://dzb.swu.edu.cn/')

    def test_html_fetch_keeps_redirect_base_url(self):
        from io import BytesIO
        from email.message import Message
        from backend.collector import fetch_html
        class Response(BytesIO):
            headers=Message()
            headers['Content-Type']='text/html; charset=utf-8'
            def geturl(self):return 'https://dzb.swu.edu.cn/cn/index.htm'
            def __enter__(self):return self
            def __exit__(self,*args):self.close()
        class Opener:
            def open(self,*args,**kwargs):return Response(b'<li>test</li>')
        with patch('backend.collector.validate_fetch_url'):
            html,base=fetch_html(Opener(),'https://dzb.swu.edu.cn/','test-agent',1000)
        self.assertEqual('https://dzb.swu.edu.cn/cn/index.htm',base)
        self.assertEqual('<li>test</li>',html)

    def test_explicit_standard_port_uses_exact_proxy_bypass_target(self):
        from backend.collector import validate_fetch_url
        with patch('socket.getaddrinfo',return_value=FAKE),patch('urllib.request.getproxies',return_value={'https':'http://127.0.0.1:7890'}),patch('urllib.request.proxy_bypass',side_effect=lambda host:host=='dzb.swu.edu.cn:443'):
            with self.assertRaises(ValueError):validate_fetch_url('https://dzb.swu.edu.cn:443/')

    def test_missing_year_is_not_invented(self):
        self.assertEqual([],extract_notices('<li><span>09-18</span><a href="info/1.htm">学校党委常委会召开会议</a></li>','https://dzb.swu.edu.cn/'))

if __name__=='__main__':unittest.main()
