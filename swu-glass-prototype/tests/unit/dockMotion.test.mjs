import test from 'node:test';
import assert from 'node:assert/strict';
import {dockInfluence} from '../../src/data/dockMotion.js';
test('Dock magnification peaks at the cursor, tapers symmetrically and stops outside the radius',()=>{
 assert.equal(dockInfluence(0),1);
 assert.equal(dockInfluence(60),dockInfluence(-60));
 assert.ok(dockInfluence(30)>dockInfluence(60));
 assert.ok(dockInfluence(60)>0);
 assert.equal(dockInfluence(120),0);
 assert.equal(dockInfluence(200),0);
});
