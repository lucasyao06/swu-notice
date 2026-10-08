import test from 'node:test';
import assert from 'node:assert/strict';
import {blankEvent,eventPayload,createCalendarRepository} from '../../src/data/calendarRepository.js';

test('task defaults and payload support inbox and new fields',()=>{
 const task=blankEvent('');
 assert.equal(task.date,'');assert.equal(task.list_id,null);assert.deepEqual(task.subtasks,[]);assert.equal(task.repeat,'none');assert.equal(task.repeat_until,'');
 const payload=eventPayload({...task,list_id:3,subtasks:[{id:'a',title:'步骤',completed:true}],repeat:'weekly',repeat_until:'2027-01-01'});
 assert.equal(payload.list_id,3);assert.equal(payload.subtasks[0].completed,true);assert.equal(payload.repeat,'weekly');assert.equal(payload.repeat_until,'2027-01-01');
});
test('demo list CRUD keeps tasks when removing a list and isolates repositories',async()=>{
 const repo=createCalendarRepository('demo'); const list=await repo.saveList({name:'学习',color:'blue'});
 const task=await repo.save({...blankEvent(''),title:'无日期任务',list_id:list.id});
 assert.equal(task.remind_at,null);assert.equal(task.repeat,'none');
 await repo.saveList({name:'研究',color:'teal'},list.id);assert.equal((await repo.lists())[0].name,'研究');
 await repo.removeList(list.id);assert.deepEqual(await repo.lists(),[]);assert.equal((await repo.list())[0].list_id,null);
 assert.deepEqual(await createCalendarRepository('demo').list(),[]);
});
test('demo recurring completion advances once, resets subtasks and clamps month end',async()=>{
 const repo=createCalendarRepository('demo'); const task=await repo.save({...blankEvent('2027-01-31'),title:'月度',repeat:'monthly',subtasks:[{id:'a',title:'步骤',completed:true}]});
 const done=await repo.save({completed:true},task.id);assert.equal(done.next_event.date,'2027-02-28');assert.equal(done.next_event.completed,false);assert.equal(done.next_event.subtasks[0].completed,false);
 await repo.save({completed:false},task.id);await repo.save({completed:true},task.id);assert.equal((await repo.list()).length,2);
});
test('daily and weekly recurrence obey inclusive ending date',async()=>{
 for(const [repeat,date] of [['daily','2026-10-01'],['weekly','2026-10-07']]){
  const repo=createCalendarRepository('demo');const task=await repo.save({...blankEvent('2026-09-30'),title:'重复',repeat,repeat_until:date});
  const done=await repo.save({completed:true},task.id);assert.equal(done.next_event.date,date);
  const last=await repo.save({completed:true},done.next_event.id);assert.equal(last.next_event??null,null);assert.equal((await repo.list()).length,2);
 }
});
test('live repository normalizes old records and uses list endpoints',async()=>{
 const calls=[];const repo=createCalendarRepository('live',async(path,options)=>{calls.push([path,options]);return path.endsWith('/events')?{items:[{id:1,title:'旧任务'}]}:options?.method?{id:2,name:'学习',color:'blue'}:{items:[]}});
 assert.equal((await repo.list())[0].repeat,'none');assert.deepEqual(await repo.lists(),[]);await repo.saveList({name:'学习',color:'blue'});await repo.saveList({name:'学习'},2);await repo.removeList(2);
 assert.deepEqual(calls.slice(1).map(([path,options])=>[path,options?.method]),[['/calendar/lists',undefined],['/calendar/lists','POST'],['/calendar/lists/2','PATCH'],['/calendar/lists/2','DELETE']]);
});
