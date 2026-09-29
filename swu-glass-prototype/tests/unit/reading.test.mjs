import {test} from 'node:test';import assert from 'node:assert/strict';import {showReadingState} from '../../src/data/reading.js';
test('reading indicators are limited to subscribed or explicitly important notices',()=>{
 const subs={sources:[1],categories:['教学教务'],keywords:['奖学金']};const n={sourceId:9,category:'校园服务',title:'普通动态'};
 assert.equal(showReadingState(n,subs),false);
 for(const patch of [{sourceId:1},{category:'教学教务'},{title:'奖学金评选'},{important:true},{badge:'重要'}])assert.equal(showReadingState({...n,...patch},subs),true);
 assert.equal(showReadingState({...n,badge:'新发布'},subs),false);
});
