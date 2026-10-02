import test from 'node:test';
import assert from 'node:assert/strict';
import {createCompetitionRepository,createCompetitionDemoRepository} from '../../src/data/competitionRepository.js';

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
