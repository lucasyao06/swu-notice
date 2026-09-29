"""Isolated integration API: never opens the user's persistent database."""
import sys,tempfile
from pathlib import Path
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from backend.store import Store
from backend.server import MonitorServer,ALLOWED_ORIGINS
ALLOWED_ORIGINS.add('http://127.0.0.1:5181')
with tempfile.TemporaryDirectory(prefix='swu-api-test-') as directory:
    store=Store(Path(directory)/'test.sqlite3',root/'data/sites.json')
    store.db.execute("UPDATE notices SET is_demo=0,date_verified=1,url='https://www.swu.edu.cn/info/'||id")
    store.db.execute('UPDATE messages SET is_demo=0')
    for i in range(3):
        store.db.execute("INSERT INTO notices(source_id,title,published_at,category,summary,url,is_demo,date_verified,created_at) VALUES(11,?,'2026-09-20','教学教务','测试摘要',?,0,1,'2026-09-20')",(f'接口测试通知{i}',f'https://www.swu.edu.cn/test/{i}'))
    store.db.commit()
    sub=store.get_subscriptions();store.save_subscriptions(sub['sources'],sub['keywords'],sub['categories'],False)
    server=MonitorServer(('127.0.0.1',8876),store)
    print('fixture ready',flush=True)
    try:server.serve_forever()
    finally:server.server_close();store.close()
