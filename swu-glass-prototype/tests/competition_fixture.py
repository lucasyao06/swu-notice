import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'swu-notice-monitor'))
from backend.store import Store
from backend.server import MonitorServer

root=Path(__file__).resolve().parents[2]/'swu-notice-monitor'
with tempfile.TemporaryDirectory() as temp:
    campus=Store(Path(temp)/'fixture.db',root/'data/sites.json')
    server=MonitorServer(('127.0.0.1',8877),campus)
    competitions=server.competitions
    source=competitions.sources('cumcm')[0]
    competitions.save_subscriptions(['cumcm'])
    competitions.checkpoint(source['id'],{},'正常',complete=True)
    for i in range(13):
        competitions.upsert_notice(source,{'title':f'联调数学建模比赛报名通知{i+1}','url':f'https://www.mcm.edu.cn/fixture/{i}',
            'published_at':date.today().isoformat(),'kind':'报名','attachments':[]})
    law_source=competitions.sources('tianxin-judgment')[0]
    for i in range(2):
        competitions.upsert_notice(law_source,{'title':f'联调天欣杯裁判文书写作大赛报名通知{i+1}',
            'url':f'https://www5.zzu.edu.cn/newlaw/fixture/{i}','published_at':date.today().isoformat(),
            'kind':'报名','attachments':[]})
    try: server.serve_forever()
    finally: server.server_close();campus.close()
