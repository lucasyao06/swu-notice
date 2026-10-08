const {dockNavigate}=require('./helpers/dock.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');const assert=require('node:assert/strict');
(async()=>{const b=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});try{
const p=await b.newPage({viewport:{width:1280,height:720},timezoneId:'Asia/Shanghai'});const errors=[];p.on('pageerror',e=>errors.push(e.message));
await p.clock.install({time:new Date('2026-09-29T16:59:50+08:00')});await p.goto('http://127.0.0.1:5180/?mode=demo');await p.locator('.light-day').waitFor();await p.clock.fastForward(16000);await p.locator('.light-sunset').waitFor();
await dockNavigate(p,'设置');const select=p.getByRole('combobox',{name:'光线氛围'});assert.equal(await select.inputValue(),'auto');
await p.clock.setSystemTime(new Date('2026-09-29T19:00:00+08:00'));await p.evaluate(()=>window.dispatchEvent(new Event('focus')));await p.locator('.light-moonlight').waitFor();
await select.selectOption('sunset');await p.locator('.light-sunset').waitFor();await p.reload();await p.locator('.light-sunset').waitFor();
await p.waitForTimeout(2600);await p.screenshot({path:'docs/lighting-sunset.png'});
await dockNavigate(p,'设置');await select.selectOption('auto');await p.locator('.light-moonlight').waitFor();await dockNavigate(p,'首页');await p.waitForTimeout(2600);await p.screenshot({path:'docs/lighting-moonlight.png'});
assert.ok(await p.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1));
await dockNavigate(p,'设置');await p.getByRole('switch',{name:'自然光效'}).click();assert.equal(await p.locator('.ambient-layer.is-active .ambient-rays').evaluate(e=>getComputedStyle(e).animationName),'none');
await p.getByRole('switch',{name:'自然光效'}).click();await p.emulateMedia({reducedMotion:'reduce'});assert.equal(await p.locator('.ambient-layer.is-active .ambient-rays').evaluate(e=>getComputedStyle(e).animationName),'none');
await p.clock.setSystemTime(new Date('2026-09-30T05:00:00+08:00'));await p.evaluate(()=>window.dispatchEvent(new Event('focus')));await p.locator('.light-morning').waitFor();assert.deepEqual(errors,[]);
console.log('Lighting browser passed: automatic boundaries, focus recalibration, manual persistence, sunset/moonlight screenshots, quiet/reduced motion, viewport fit.');
}finally{await b.close()}})().catch(e=>{console.error(e);process.exit(1)});
