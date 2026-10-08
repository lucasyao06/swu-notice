const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const {dockNavigate}=require('./helpers/dock.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  for(const width of [1440,1280,1024,768,390])for(const phase of ['day','moonlight']){
   const page=await browser.newPage({viewport:{width,height:900},timezoneId:'Asia/Shanghai',reducedMotion:'reduce'});
   const errors=[];page.on('pageerror',error=>errors.push(error.message));
   await page.addInitScript(value=>localStorage.setItem('swu-glass:lighting-mode',JSON.stringify(value)),phase);
   await page.goto('http://127.0.0.1:5180/?mode=demo');await dockNavigate(page,'日程');
   const tabs=page.locator('[aria-label="日程视图切换"]');
   const before=await tabs.boundingBox();
   for(const view of ['月','清单','周']){
    await tabs.getByRole('button',{name:view,exact:true}).click();
    const after=await tabs.boundingBox();
    assert.ok(Math.abs(before.x-after.x)<=1&&Math.abs(before.y-after.y)<=1,`${width}/${phase}: view controls moved when switching to ${view}: ${JSON.stringify({before,after})}`);
    if(view==='月'&&width>=1000){
     const main=await page.locator('.schedule-main').boundingBox(),agenda=await page.locator('.agenda-panel').boundingBox();
     assert.ok(Math.abs(main.y-agenda.y)<=1,`${width}/${phase}: month and agenda must align at the top`);
     assert.ok(Math.abs(main.y+main.height-agenda.y-agenda.height)<=1,`${width}/${phase}: month and agenda must align at the bottom`);
    }
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'No horizontal page overflow');
    if(width>=1000)assert.ok(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1),'Desktop views must fit the viewport');
   }
   if(width===1440&&phase==='moonlight'){
    await tabs.getByRole('button',{name:'月',exact:true}).click();
    await page.screenshot({path:'/private/tmp/schedule-toolbar-month.png'});
   }
   assert.deepEqual(errors,[]);await page.close();
  }
  console.log('Schedule toolbar passed: fixed view controls, aligned month/agenda panels, day/night and desktop/mobile fit.');
 }finally{await browser.close()}
})().catch(error=>{console.error(error);process.exit(1)});
