const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const {dockNavigate}=require('./helpers/dock.cjs');
const overlap=(a,b)=>a.x<b.x+b.width&&a.x+a.width>b.x&&a.y<b.y+b.height&&a.y+a.height>b.y;
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  for(const [width,height] of [[1513,1039],[1440,900],[1280,720],[1024,680],[768,900],[390,844]]){
   for(const theme of ['day','moonlight']){
    const page=await browser.newPage({viewport:{width,height},reducedMotion:'reduce'});
    await page.addInitScript(theme=>localStorage.setItem('swu-glass:lighting-mode',JSON.stringify(theme)),theme);
    await page.route('**/api/**',route=>{const path=new URL(route.request().url()).pathname;const json=path==='/api/notices'?{items:[],total:116091}:path==='/api/subscriptions'?{sources:[],keywords:[],categories:[],in_app:true}:path==='/api/messages'?{items:[],unread:0}:{items:[]};return route.fulfill({json})});
    await page.goto('http://127.0.0.1:5180');
    for(const name of ['通知','订阅','来源','日程']){
     await dockNavigate(page,name);await page.mouse.move(10,10);await page.locator('.loading-status').waitFor({state:'hidden'});
     if(width<1000)await page.evaluate(()=>window.scrollTo(0,document.documentElement.scrollHeight));
     const handle=page.getByRole('button',{name:'展开导航栏',exact:true}),trigger=await handle.boundingBox();
     if(width>=1000){const content=await page.locator('.content-grid').boundingBox();assert.ok(height-content.y-content.height<=24,`${width}/${theme}/${name}: hidden Dock must not reserve a large empty band`);}
     const controls=await page.locator('.pagination>button,.pagination>span,.page-jump-control,.workspace-actions>button,.calendar-key>span').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect();return {class:e.className,x:r.x,y:r.y,width:r.width,height:r.height}}));
     for(const control of controls)assert.ok(!overlap(trigger,control),`${width}/${theme}/${name}: Dock trigger overlaps ${control.class}`);
     if(name==='通知'){
      const slider=await page.getByRole('slider',{name:'滑动跳转页码'}).boundingBox(),number=await page.getByRole('spinbutton',{name:'跳转页码'}).boundingBox();
      assert.ok(!overlap(slider,number),'range and numeric input stay separate');
      assert.ok(await page.evaluate(({x,y})=>!!document.elementFromPoint(x,y)?.closest('.page-number'),{x:number.x+3,y:number.y+number.height/2}),'Dock handle must not intercept the page input');
      await page.getByRole('spinbutton',{name:'跳转页码'}).fill('100');await page.getByRole('spinbutton',{name:'跳转页码'}).press('Enter');
      await page.getByText('共 116,091 条 · 100 / 19349 页',{exact:true}).waitFor();
     }
     await handle.hover();const dock=await page.locator('.dock').boundingBox();
     assert.ok(dock.y>=0&&dock.y+dock.height<=height,'expanded overlay stays in the viewport');
     assert.ok(Math.abs(trigger.y+trigger.height/2-dock.y-dock.height/2)<1,'reserve space without changing the shared Dock center');
     assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'no horizontal overflow');
     if(width>=1000)assert.ok(await page.evaluate(()=>document.documentElement.scrollHeight<=innerHeight+1),'desktop still fits one screen');
     if(width===1280&&name==='通知'){
      await page.mouse.move(10,10);await page.locator('.pagination-jump').screenshot({path:`docs/pagination-clear-${theme}.png`});await page.screenshot({path:`docs/bottom-clear-${theme}.png`});
     }
    }
    await page.close();
   }
   console.log(`${width}x${height}: day/night: content fills viewport, collapsed handle avoids controls, expanded Dock overlays without reflow`);
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
