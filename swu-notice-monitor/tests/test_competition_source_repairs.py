"""Public website payload variants and failure semantics, without network IO."""
import gzip
import io
import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.response
from datetime import date, datetime, timezone
from email.message import Message
from pathlib import Path
from unittest.mock import patch

from backend.competition_collector import (OfficialFetcher, OfficialContentDecoder,
    classify, collect_source, parse_listing, safe_link)
from backend.competition_store import CompetitionStore
from backend.store import Store

ROOT=Path(__file__).resolve().parents[1]


class PublicPayloadTests(unittest.TestCase):
    def test_structured_attachment_and_custom_id_paging(self):
        body={'code':0,'data':{'current':1,'pages':2,'records':[
            {'newsId':123,'newsTitle':'全国智能机器人创意大赛延期通知',
             'publishTime':date.today().isoformat(),'newsFiles':[
                 {'fileName':'正式通知.pdf','fileUrl':'https://files.example.org/延期通知.pdf'}]}]}}
        config={'json_items_path':'data.records','json_id_field':'newsId',
            'json_url_template':'https://example.org/home/newsDetails?newsId={id}',
            'json_attachments':{'field':'newsFiles','url':'fileUrl','title':'fileName'},
            'json_pagination':{'parameter':'pageNum','current':'data.current','total_pages':'data.pages'}}
        rows,links=parse_listing(json.dumps(body),'https://example.org/api?pageNum=1',config)
        self.assertEqual('https://example.org/home/newsDetails?newsId=123',rows[0]['url'])
        self.assertEqual('变更',rows[0]['kind'])
        self.assertIn('%E5%BB%B6',rows[0]['attachments'][0]['url'])
        self.assertTrue(rows[0]['detail_complete'])
        self.assertEqual(['https://example.org/api?pageNum=2'],links)

    def test_declared_epoch_only_and_total_row_pagination(self):
        stamp=int(datetime(2026,1,1,23,tzinfo=timezone.utc).timestamp())
        payload={'total':21,'datalist':[{'nnid':22,'title':'蓝桥杯全国总决赛报名通知','publishTime':str(stamp*1000)}]}
        config={'json_items_path':'datalist','json_id_field':'nnid',
            'json_url_template':'https://example.org/notices/{id}/','json_date_epoch':'milliseconds',
            'json_pagination':{'parameter':'pageno','total_items':'total','size_parameter':'pagesize'}}
        rows,links=parse_listing(json.dumps(payload),'https://example.org/api?pageno=1&pagesize=20',config)
        self.assertEqual('2026-01-02',rows[0]['published_at'])
        self.assertIn('pageno=2',links[0])
        rows,_=parse_listing(json.dumps(payload),'https://example.org/',{**config,'json_date_epoch':None})
        self.assertEqual('',rows[0]['published_at'])

    def test_attachment_original_never_uses_creation_date(self):
        payload={'data':[{'title':'第二轮通知','createtime':'2026-01-01',
            'content':'<a href="https://example.org/notice.pdf">大学生信息素养大赛报名通知.pdf</a>'}]}
        rows,_=parse_listing(json.dumps(payload),'https://example.org/',{
            'json_items_path':'data','json_fields':{'date':[]},
            'json_attachment_original':True,'json_title_from_attachment':True})
        self.assertEqual('https://example.org/notice.pdf',rows[0]['url'])
        self.assertEqual('大学生信息素养大赛报名通知',rows[0]['title'])
        self.assertEqual('',rows[0]['published_at'])

    def test_api_error_is_failure_instead_of_empty_announcements(self):
        with self.assertRaisesRegex(ValueError,'URL路径不合法'):
            parse_listing('{"code":402,"msg":"URL路径不合法"}','https://example.org/',
                {'json_success':{'path':'code','value':0}})

    def test_uuid_and_injected_identifier(self):
        config={'json_url_template':'https://example.org/article/{id}'}
        payload=[{'id':'abc-123','title':'大学生大赛报名通知'},
                 {'id':'../../private?x=1','title':'大学生大赛报名通知'}]
        rows,_=parse_listing(json.dumps(payload),'https://example.org/',config)
        self.assertEqual(1,len(rows))

    def test_filters_organizer_recruitment_and_training_but_keeps_results(self):
        for title in ['公开征集全国大赛办赛方案的公告','蓝桥杯培训及开发者认证的通知',
            '全国大赛总结','全国大赛颁奖典礼通知']:
            self.assertIsNone(classify(title),title)
        self.assertEqual('报名',classify('ICPC亚洲区域赛邀请函'))
        self.assertEqual('规则',classify('ICPC区域赛名额分配方案'))
        self.assertEqual('赛程',classify('2026 CCPC 各场比赛安排'))

    def test_gzip_bounded_decode_and_redirect_metadata(self):
        headers=Message();headers['Content-Encoding']='gzip'
        response=urllib.response.addinfourl(io.BytesIO(gzip.compress(b'<html>ok</html>')),headers,'https://example.org/',200)
        response.msg='OK'
        decoded=OfficialContentDecoder().http_response(None,response)
        self.assertEqual(b'<html>ok</html>',decoded.read())
        self.assertEqual('OK',decoded.msg)
        response=urllib.response.addinfourl(io.BytesIO(gzip.compress(b'x'*1_500_001)),headers,'https://example.org/',200)
        response.msg='OK'
        with self.assertRaisesRegex(ValueError,'解压页面超过'):OfficialContentDecoder().http_response(None,response)

    def test_robots_redirect_never_recursively_reads_policy(self):
        fetcher=OfficialFetcher({'url':'https://example.org/'},threading.Event())
        policy=type('Policy',(),{'can_fetch':lambda *args:False})()
        def load(*args):
            fetcher._check_robots('https://example.org/home')
            return policy
        with patch('backend.competition_collector.read_robots',side_effect=load) as read:
            with self.assertRaisesRegex(ValueError,'robots.txt'):fetcher._check_robots('https://example.org/news')
        self.assertEqual(1,read.call_count)
        self.assertFalse(fetcher.reading_robots)

    def test_public_post_list_body_only_applies_to_list_url(self):
        config={'url':'https://example.org/','list_url':'https://example.org/api/list?page=1',
            'request_json':{'page':1,'rows':20},'json_pagination':{'parameter':'page'}}
        fetcher=OfficialFetcher(config,threading.Event())
        policy=type('Policy',(),{'can_fetch':lambda *args:True,'crawl_delay':lambda *args:0})()
        requests=[]
        def open_request(req,**kwargs):
            requests.append(req)
            headers=Message();headers['Content-Type']='application/json'
            return urllib.response.addinfourl(io.BytesIO(b'{}'),headers,req.full_url,200)
        with patch('backend.competition_collector.check_url'),patch('backend.competition_collector.read_robots',return_value=policy),patch.object(fetcher.opener,'open',side_effect=open_request):
            fetcher('https://example.org/api/list?page=2')
            fetcher('https://example.org/article/1')
        self.assertEqual({'page':2,'rows':20},json.loads(requests[0].data))
        self.assertEqual('GET',requests[1].get_method())


class CollectionRepairTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.campus=Store(Path(self.temp.name)/'db.sqlite',ROOT/'data/sites.json')
        self.store=CompetitionStore(self.campus)
        self.source=self.store.sources('cumcm')[0]

    def tearDown(self):
        self.campus.close();self.temp.cleanup()

    def test_verified_empty_column_sets_baseline_but_js_shell_does_not(self):
        source={**self.source,'config':{**self.source['config'],'keywords':['数学建模'],
            'verified_empty_listing':True,'detail_fetch':False}}
        html=f'<li><a href="/n/1">其他大赛报名通知</a><time>{date.today()}</time></li>'
        result=collect_source(self.store,source,lambda url:(html,url))
        self.assertEqual('正常',result['status'])
        self.assertTrue(self.store.sources('cumcm')[0]['baseline'])
        self.assertEqual(0,self.store.list_notices()['total'])
        self.assertIn('未发现对应赛事',self.store.sources('cumcm')[0]['error'])
        result=collect_source(self.store,source,lambda url:('<div id="app"></div>',url))
        self.assertEqual('解析受限',result['status'])

    def test_public_detail_api_keeps_original_url_and_favorite(self):
        today=date.today().isoformat();base=self.source['config']['url']
        config={**self.source['config'],'json_items_path':'data.records',
            'json_url_template':base+'details/{id}','json_detail_url_template':base+'api/detail?id={id}',
            'json_content_field':'newsInfo','json_attachment_urls':['pdfInfo']}
        source={**self.source,'config':config}
        row={'id':42,'title':'全国大学生数学建模竞赛报名通知','publishTime':today}
        notice,_=self.store.upsert_notice(source,{'title':row['title'],'url':base+'details/42',
            'published_at':today,'kind':'报名','attachments':[{'title':'保留附件','url':base+'keep.pdf'}]})
        self.store.update_notice(notice['id'],{'read':True,'favorite':True})
        pages={base:json.dumps({'data':{'records':[row]}}),
            base+'api/detail?id=42':json.dumps({'data':{**row,'newsInfo':'正式正文','pdfInfo':base+'rules.pdf'}})}
        result=collect_source(self.store,source,lambda url:(pages[url],url))
        self.assertEqual('正常',result['status'])
        result=self.store.get_notice(notice['id'])
        self.assertEqual(base+'details/42',result['url'])
        self.assertTrue(result['read'] and result['favorite'])
        self.assertIn(base+'rules.pdf',[a['url'] for a in result['attachments']])
        self.assertEqual(0,self.store.list_messages()['total'])


if __name__=='__main__':unittest.main()
