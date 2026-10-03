import json
import tempfile
import unittest
from pathlib import Path

from backend.store import Store
from backend.competition_store import CompetitionStore

ROOT = Path(__file__).resolve().parents[1]


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.campus = Store(Path(self.temp.name) / 'test.db', ROOT / 'data/sites.json')
        self.store = CompetitionStore(self.campus)

    def tearDown(self):
        self.campus.close()
        self.temp.cleanup()

    def rule(self, identity):
        return self.store.reference(identity, 'engineering')['reference_rules'][0]

    def test_coverage_and_no_guessed_challenge(self):
        self.assertEqual(73, self.store.list_catalog(scope='all')['total'])
        self.assertEqual(21, self.store.list_catalog(college_id='engineering')['total'])
        self.assertEqual(19, self.store.list_catalog(college_id='engineering', category='学科竞赛')['total'])
        self.assertEqual(2, self.store.list_catalog(college_id='engineering', category='创新创业')['total'])
        for identity in ('challenge', 'challenge-business'):
            self.assertEqual([], self.store.reference(identity, 'engineering')['reference_rules'])
        pending = self.store.college('engineering')['unassociated_rules'][0]
        self.assertEqual('赛种待确认', pending['status'])
        self.assertEqual([[35,25,20,15],[15,10,5,3.5],[5,3.5,2.5,1]], [x['scores'] for x in pending['levels']])
        self.assertEqual([], self.store.sources('engineering-electronic-unconfirmed'))
        self.assertEqual([], self.store.reference('nuedc', 'engineering')['reference_rules'])

    def test_exact_multilevel_fractional_rules(self):
        expected = {
            'mcm-icm': [[30,25,15,10,2]], 'cumcm': [[25,20,15],[15,10,5],[8,5,3]],
            'engineering-electronic-unconfirmed': [[25,20,15],[15,10,5],[8,5,3]],
            'math': [[25,20,15],[5,3.5,2.5],[2,1.5,1]],
            'cq-innovation-method': [[7,5,3.5,2.5]], 'neccs': [[10,5,2.5],[2.5,1.5,1],[1,.75,.5]],
            'cq-mobile-robot': [[5,3.5,2.5]], 'smartcar': [[25,20,15],[15,10,5]],
            'caairobot': [[25,20,15]], 'bochuang': [[15,10,5]], 'agricultural-equipment': [[15,10,5]],
            'mechanical-design': [[15,10,5]], 'advanced-drawing': [[15,10,5],[5,3.5,2.5]],
            'engineering-egs': [[2,1.5,1]], 'agricultural-building': [[15,10,5]],
            'zhou-peiyuan': [[20,15,10],[8,5,3]], 'cq-mechanics': [[5,3.5,2.5]],
            'engineering-practice': [[25,20,15],[15,10,5]], 'structure-design': [[25,20,15],[15,10,5],[8,5,3]],
            'innovation': [[35,25,20,15],[15,10,5,3.5],[5,3.5,2.5,1]], 'hanhong-academic': [[5,3.5,2.5,1]],
        }
        for identity, values in expected.items():
            with self.subTest(identity=identity):
                self.assertEqual(values, [x['scores'] for x in self.rule(identity)['levels']])
        self.assertEqual(['O','F','M','H','S'], self.rule('mcm-icm')['levels'][0]['awards'])
        self.assertIn('第四等级奖（如有）', self.rule('innovation')['levels'][1]['awards'])

    def test_conflicts_period_and_incomplete_notes(self):
        self.assertIn('智能汽车', self.rule('caairobot')['conflicts'][0])
        self.assertIn('待学院确认', self.rule('caairobot')['conflicts'][0])
        for identity in ('innovation', 'hanhong-academic'):
            period = self.rule(identity)['applicable_period']
            self.assertEqual(('2025-09-01','2026-08-31'), (period['start'], period['end']))
            self.assertTrue(any('没有负责人' in x and '50%' in x for x in self.rule(identity)['notes']))
        self.assertNotIn('applicable_period', self.rule('mcm-icm'))
        academic = ' '.join(self.rule('mcm-icm')['notes'])
        self.assertIn('0.8', academic)
        self.assertIn('截断', academic)
        self.assertNotIn('50%', academic)
        self.assertIn('组别认定范围待确认', ' '.join(self.rule('math')['notes']))
        self.assertIn('智能车团体赛', self.rule('bochuang')['default_level'])

    def test_shared_scores_and_global_personal_state(self):
        source = self.store.sources('hanhong-academic')[0]
        self.store.save_subscriptions(['hanhong-academic'])
        item = {'title':'含弘杯参赛通知','kind':'报名','published_at':'','url':'https://gqt.swu.edu.cn/info/fixture','attachments':[]}
        notice, _ = self.store.upsert_notice(source, item)
        self.assertEqual(0, self.store.list_messages()['total'])
        self.store.checkpoint(source['id'], {}, '正常', complete=True)
        item['url'] += '/new'
        notice, _ = self.store.upsert_notice(source, item)
        self.store.upsert_notice(source, item)
        self.store.update_notice(notice['id'], {'favorite':True,'read':True}, 'engineering')
        self.assertEqual(1, self.store.list_messages(college_id='law')['total'])
        self.assertEqual(5, self.store.get_notice(notice['id'], 'engineering')['reference_rules'][0]['levels'][0]['scores'][0])
        self.assertEqual(25, self.store.get_notice(notice['id'], 'law')['reference_rules'][0]['levels'][0]['scores'][0])
        self.assertTrue(self.store.get_notice(notice['id'], 'law')['favorite'])
        self.assertTrue(self.store.get_notice(notice['id'], 'cis')['read'])
        self.assertEqual([], self.store.get_notice(notice['id'], 'cis')['reference_rules'])
        self.assertEqual(30, self.store.reference('innovation', 'cis')['reference_rules'][0]['levels'][0]['scores'][1])
        self.assertEqual(25, self.store.reference('innovation', 'law')['reference_rules'][0]['levels'][0]['scores'][0])
        self.assertEqual(35, self.rule('innovation')['levels'][0]['scores'][0])

    def test_incremental_addition_preserves_old_rows_and_baselines(self):
        catalog = json.loads((ROOT/'data/competitions.json').read_text(encoding='utf8'))
        rules = json.loads((ROOT/'data/college_competition_rules.json').read_text(encoding='utf8'))
        old_rules = {**rules, 'colleges':[x for x in rules['colleges'] if x['id']!='engineering'],
            'rules':[x for x in rules['rules'] if x['college_id']!='engineering']}
        old_ids = {x['competition_id'] for x in old_rules['rules']}
        old_catalog = {**catalog, 'items':[x for x in catalog['items'] if x['id'] in old_ids]}
        path = Path(self.temp.name)
        (path/'competitions.json').write_text(json.dumps(old_catalog), encoding='utf8')
        (path/'college_competition_rules.json').write_text(json.dumps(old_rules), encoding='utf8')
        old_campus = Store(path/'before.db', ROOT/'data/sites.json')
        try:
            previous = CompetitionStore(old_campus, catalog_path=path/'competitions.json')
            source = previous.sources('cumcm')[0]
            previous.save_subscriptions(['cumcm'])
            previous.checkpoint(source['id'], {'visited':['keep']}, '正常', complete=True)
            n,_ = previous.upsert_notice(source, {'title':'数学建模报名通知','kind':'报名','published_at':'','url':'https://www.mcm.edu.cn/fixture','attachments':[]})
            previous.update_notice(n['id'], {'read':True,'favorite':True})
            tables = [r[0] for r in old_campus.db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
            before = {t:[tuple(r) for r in old_campus.db.execute(f'SELECT * FROM "{t}" ORDER BY rowid')] for t in tables}
            CompetitionStore(old_campus, catalog_path=ROOT/'data/competitions.json')
            for table, rows in before.items():
                after = [tuple(r) for r in old_campus.db.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
                if table in ('competitions','competition_colleges','competition_college_rules','competition_sources'):
                    self.assertTrue(set(rows)<=set(after), table)
                else:self.assertEqual(rows, after, table)
        finally:old_campus.close()

    def test_manual_sources_are_scoped_but_global_schedule_remains_global(self):
        sources = self.store.sources(college_id='engineering')
        ids = {r['id'] for r in self.store.list_catalog(college_id='engineering')['items']}
        self.assertTrue({x['competition_id'] for x in sources} <= ids)
        self.assertGreater(len(self.store.sources()), len(sources))
        self.assertEqual(1, len(self.store.sources('hanhong-academic')))


if __name__ == '__main__': unittest.main()
