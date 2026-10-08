import test from 'node:test';
import assert from 'node:assert/strict';
import * as schedule from '../../src/data/schedule.js';

test('quick capture respects today, inbox, unscheduled and custom list contexts',()=>{
 assert.equal(typeof schedule.quickTaskDefaults,'function');
 assert.deepEqual(schedule.quickTaskDefaults({range:'today',today:'2026-10-04',listId:null,category:'study'}),{date:'2026-10-04',list_id:null,category:'study'});
 for(const range of ['all','inbox','unscheduled','upcoming','overdue'])assert.equal(schedule.quickTaskDefaults({range,today:'2026-10-04'}).date,'');
 assert.deepEqual(schedule.quickTaskDefaults({range:'today',today:'2026-10-04',listId:3}),{date:'',list_id:3,category:'other'});
});
test('quick date shortcuts cross month, year and leap-day boundaries',()=>{
 assert.equal(typeof schedule.shiftDate,'function');
 assert.equal(schedule.shiftDate('2026-12-31',1),'2027-01-01');
 assert.equal(schedule.shiftDate('2028-02-28',1),'2028-02-29');
 assert.equal(schedule.shiftDate('2026-10-01',-1),'2026-09-30');
});
test('reminder time includes offset, lead time and the all-day 09:00 default',()=>{
 assert.equal(typeof schedule.reminderDateTime,'function');
 assert.equal(schedule.reminderDateTime({date:'2026-10-04',time:'09:00',timezone_offset:480,reminder_minutes:15}).toISOString(),'2026-10-04T00:45:00.000Z');
 assert.equal(schedule.reminderDateTime({date:'2026-10-04',time:'',timezone_offset:480,reminder_minutes:1440}).toISOString(),'2026-10-03T01:00:00.000Z');
 assert.equal(schedule.reminderDateTime({date:'',reminder_minutes:0}),null);
 assert.equal(schedule.reminderDateTime({date:'2026-10-04',reminder_minutes:null}),null);
});
