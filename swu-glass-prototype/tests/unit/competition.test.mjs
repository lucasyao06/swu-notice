import test from 'node:test';
import assert from 'node:assert/strict';
import {createCompetitionRepository,createCompetitionDemoRepository} from '../../src/data/competitionRepository.js';
import {competitionMatchesQuery} from '../../src/data/competitionRules.js';

test('competition API uses its own namespace and bounded pagination',async()=>{
 const paths=[];const repo=createCompetitionRepository(async(path,options)=>{paths.push([path,options]);return {items:[],total:0}});
 await repo.notices({q:'数学',competition:'cumcm',kind:'报名',tab:'following',page:2});
 const params=new URLSearchParams(paths[0][0].split('?')[1]);
 assert.equal(paths[0][0].split('?')[0],'/competition/notices');assert.equal(params.get('offset'),'20');assert.equal(params.get('limit'),'10');
 await repo.follow(['ccpc']);assert.equal(paths[1][0],'/competition/subscriptions');assert.deepEqual(paths[1][1].body,{competitions:['ccpc']});
 await repo.readMessage();assert.equal(paths[2][0],'/competition/messages');assert.deepEqual(paths[2][1].body,{read:true});
});
test('demo catalogue retains scoring, zero and missing values',async()=>{
 const data=await createCompetitionDemoRepository().catalog();
 assert.equal(data.items.length,44);assert.equal(data.items.find(x=>x.id==='innovation').scores[0],null);
 assert.deepEqual(data.items.find(x=>x.id==='mcm-icm').awards,['O','F','M','H','S']);
 assert.equal(data.items.find(x=>x.id==='mcm-icm').scores[4],0);
 assert.equal(data.items.filter(x=>x.parent==='中国高校计算机大赛').length,6);
});
test('demo follow, read and favorite changes stay isolated',async()=>{
 const a=createCompetitionDemoRepository(),b=createCompetitionDemoRepository();
 await a.follow([]);assert.equal((await a.notices({tab:'following'})).total,0);assert.equal((await b.notices({tab:'following'})).total,2);
 await a.update(1,{read:true,favorite:true});assert.equal((await a.messages()).unread,1);assert.equal((await a.notices({tab:'favorite'})).total,1);
 assert.equal((await b.messages()).unread,2);assert.equal((await b.notices({tab:'favorite'})).total,0);
 await a.readMessage();assert.equal((await a.messages()).unread,0);await assert.rejects(a.start(),/演示模式/);
});

test('college rules keep shared identities, decimals and conflicts without cross-college score fallback',async()=>{
 const repo=createCompetitionDemoRepository();
 assert.equal((await repo.colleges()).items.length,2);
 const law=await repo.catalog(null,{college:'law'});
 assert.equal(law.total,17);
 assert.equal(law.items.find(x=>x.id==='challenge').scores[0],25);
 assert.equal((await repo.catalog()).items.find(x=>x.id==='challenge').scores[0],30);
 assert.deepEqual(law.items.find(x=>x.id==='yingming-zhili-moot').scores,[2.5,2,1.5]);
 assert.deepEqual(law.items.find(x=>x.id==='yingming-academic').scores,[4,3,2,1]);
 const rule=law.items.find(x=>x.id==='innovation').reference_rules[0];
 assert.equal(competitionMatchesQuery(law.items.find(x=>x.id==='innovation'),'互联网＋'),true);
 assert.match(rule.conflicts[0],/25分.*20分/);
 const all=await repo.catalog(null,{college:'law',scope:'all'});
 assert.equal(all.total,59);assert.deepEqual(all.items.find(x=>x.id==='cumcm').scores,[]);
 assert.equal((await repo.catalog(null,{college:'law',category:'专业技能'})).total,12);
});

test('demo personal records remain global and carry the selected college context',async()=>{
 const repo=createCompetitionDemoRepository();
 await repo.update(1,{read:true,favorite:true},'law');
 assert.equal((await repo.notices({college:'law'})).total,1);
 const favorites=await repo.notices({college:'law',tab:'favorite'});
 assert.equal(favorites.total,1);assert.deepEqual(favorites.items[0].reference_rules,[]);
 assert.match(favorites.items[0].recognition_note,/未列名/);
 assert.equal((await repo.notices({college:'law',tab:'following'})).total,2);
 assert.equal((await repo.messages(0,null,'law')).unread,(await repo.messages()).unread);
 assert.equal((await repo.notice(1)).read,true);
 assert.equal((await repo.subscriptions()).competitions.length,2);
});
