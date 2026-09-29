import tempfile
import unittest
from pathlib import Path
from backend.store import Store

class PaginationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.tmp.name)/'db.sqlite3',Path(__file__).resolve().parents[1]/'data/sites.json')
    def tearDown(self):
        self.store.close(); self.tmp.cleanup()
    def test_pages_preserve_total_and_order(self):
        all_items=self.store.list_notices()['items']
        page=self.store.list_notices(limit=2,offset=2)
        self.assertEqual(5,page['total'])
        self.assertEqual(all_items[2:4],page['items'])
        self.assertEqual([],self.store.list_notices(limit=2,offset=100)['items'])
    def test_filtered_total(self):
        page=self.store.list_notices(q='课程',limit=1)
        self.assertEqual(1,page['total']); self.assertEqual(1,len(page['items']))
    def test_invalid_limits(self):
        for limit,offset in [(0,0),(101,0),(2,-1),(True,0)]:
            with self.assertRaises(ValueError): self.store.list_notices(limit=limit,offset=offset)
