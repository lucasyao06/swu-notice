import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolveLighting,lightingPreference} from '../../src/data/lighting.js';
test('automatic lighting uses local clock boundaries including midnight',()=>{
 for(const [hour,minute,expected] of [[0,0,'moonlight'],[4,59,'moonlight'],[5,0,'morning'],[9,59,'morning'],[10,0,'day'],[16,59,'day'],[17,0,'sunset'],[18,59,'sunset'],[19,0,'moonlight'],[23,59,'moonlight']])assert.equal(resolveLighting('auto',new Date(2026,8,29,hour,minute)),expected);
});
test('manual choice is stable regardless of system time; invalid stored mode defaults to auto',()=>{
 for(const mode of ['morning','day','sunset','moonlight'])assert.equal(resolveLighting(mode,new Date(2026,8,29,12)),mode);
 assert.equal(lightingPreference('invalid'),'auto');assert.equal(lightingPreference(null),'auto');assert.equal(lightingPreference('sunset'),'sunset');
});
