import test from 'node:test';
import assert from 'node:assert/strict';
import {weekDates,eventLanes,moveEvent} from '../../src/data/schedule.js';
test('week crosses month and year boundaries starting Monday',()=>{assert.deepEqual(weekDates('2027-01-01'),['2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01','2027-01-02','2027-01-03'])});
test('overlap groups use separate lanes but adjacent events do not',()=>{const lanes=eventLanes([{id:1,time:'09:00',end_time:'11:00'},{id:2,time:'10:00',end_time:'12:00'},{id:3,time:'12:00',end_time:'13:00'}]);assert.equal(lanes[0].lanes,2);assert.equal(lanes[1].lane,1);assert.equal(lanes[2].lanes,1)});
test('dragging preserves duration, snaps and stays within the day',()=>{const event={time:'09:00',end_time:'10:30'};const moved=moveEvent(event,'2026-10-02',613);assert.equal(moved.time,'10:15');assert.equal(moved.end_time,'11:45');assert.equal(moved.date,'2026-10-02');assert.equal(moveEvent(event,'2026-10-02',1500).end_time,'23:59');assert.equal(moveEvent(event,'2026-10-02',-100).time,'00:00')});
