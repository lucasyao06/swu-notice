"""Export the live official-source audit without copying notices or user state."""
import argparse
import collections
import json
from pathlib import Path
import urllib.request


def report(catalog, crawl, college_catalogs=None):
    counts=collections.Counter(x['status'] for x in catalog['items'])
    lines=['# 赛事官方来源核验清单','',
        f"本机检查完成时间：{crawl.get('last_finished') or '尚未完成'}。目录共 {len(catalog['items'])} 项。",
        '当前状态：'+ '；'.join(f'{k} {v} 项' for k,v in counts.items())+'。','',
        '这是本机实际访问结果的快照，页面会显示后续检查状态。正常表示识别到可用的官方参赛公告；待核验、解析受限和失败均保留条目及原因。',
        '首次回填仅保存可达栏目中最近365天的公告；无可靠发布日期的公告另行标注待核验。首次回填不生成消息。',
        'HTML详情保留附件；JSON正文保留附件；PDF公告直接保存官网附件链接，不从文件名猜测发布日期。英文原文保留原语言。','',
        '学院规则独立保存；全平台赛事不重复采集，关注、收藏、已读和消息不随学院切换删除。','']
    def cell(value):return str(value if value is not None else '').replace('|','／').replace('\n',' ').replace('\r',' ')
    for data in (college_catalogs or [catalog]):
        college=data.get('college',{'name':'计算机与信息科学学院'})
        lines+=['## '+college['name'],'',data['policy']['label']+'。','',
            *[f'- {x}' for x in data['policy']['notes']], '',
            '| 赛事（截图名称） | 类别 / 列名级别 | 奖项与参考分值 | 官方入口 | 采集状态 / 条数 | 最近检查 | 原因 / 限制 |',
            '| --- | --- | --- | --- | --- | --- | --- |']
        for item in data['items']:
            rule=item['reference_rules'][0]
            scores='；'.join(a+'：'+('未列明' if b is None else str(b)) for a,b in zip(item['awards'],item['scores']))
            link=f"[官网]({item['official_url']})" if item.get('official_url') else '待核验'
            notes='；'.join(filter(None,[item.get('error'),item.get('restriction'),*rule.get('conflicts',[])]))
            lines.append('| '+' | '.join(map(cell,[rule['screenshot_name'],rule['category']+' / '+rule['default_level'],scores,link,item['status']+' / '+str(item['notice_count']),item['last_checked'] or '尚未检查',notes]))+' |')
        lines+=['','### 分级参考标准与附注','']
        seen=set()
        for item in data['items']:
            rule=item['reference_rules'][0]
            key=json.dumps([rule['category'],rule['levels']],ensure_ascii=False)
            if key in seen:continue
            seen.add(key);lines+=['#### '+rule['category']+' · 示例：'+rule['screenshot_name'],'']
            for level in rule['levels']:
                values='；'.join(a+'：'+('未列明' if b is None else str(b)) for a,b in zip(level['awards'],level['scores']))
                lines.append('- '+level['name']+'：'+values)
            lines+=['',*[f'- {x}' for x in rule['notes']],'']
        lines+=['### 尚未接入条目的核验记录','']
        for item in data['items']:
            verification=item.get('verification')
            if verification:
                lines.append(('- '+item['name']+'：'+verification['conclusion']+' '+ ' '.join('[辅助官方依据]('+url+')' for url in verification['evidence'])).rstrip())
        lines.append('')
    lines+=['','## 已配置来源及核验依据','']
    for item in catalog['items']:
        for source in item['sources']:
            lines+=['### '+item['name'],'',
                f"- 发布机构：{source['name']}",
                f"- 采集入口：[官方公告栏目或公开接口]({source.get('list_url') or source['url']})",
                f"- 核验依据：[官方页面]({source['evidence']})",
                f"- 状态：{source['status']}；更新基线：{'已建立' if source['baseline'] else '未建立'}。"]
            for key in ('parser_note','transport_note'):
                if source.get(key):lines.append('- '+source[key])
            if source.get('error'):lines.append('- 实际原因：'+cell(source['error']))
            lines.append('')
    lines+=['## 维护','',
        '学院名称、类别及评分关联配置见 `data/college_competition_rules.json`；只改规则不重建采集基线，增加学院不修改页面分支。',
        '修改 `data/competitions.json` 中已核验来源配置后重启后端；配置变化会重建该来源基线，保留原通知的阅读与收藏状态。',
        '公开接口字段映射、分页参数和原文URL模板必须来自官网实际请求。来源不明确时保留待核验，不使用推广网站或同名其他比赛代替。',
        '运行 `python scripts/competition_report.py` 可从本地API重新生成本清单。']
    return '\n'.join(lines)+'\n'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='导出赛事官网采集状态清单')
    parser.add_argument('--api',default='http://127.0.0.1:8765/api/competition')
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'docs/competition-sources.md')
    args=parser.parse_args()
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    def read(path):
        with opener.open(args.api.rstrip('/')+'/'+path,timeout=15) as response:return json.load(response)
    catalog,crawl=read('catalog?scope=all'),read('crawl')
    college_catalogs=[read('catalog?college='+college['id']) for college in read('colleges')['items']]
    if crawl['running']:raise SystemExit('采集尚未完成；请完成检查后再导出交付快照。')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(report(catalog,crawl,college_catalogs),encoding='utf-8')
    print(f'已导出 {catalog["total"]} 项赛事来源：{args.output}')
