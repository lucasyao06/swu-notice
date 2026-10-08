const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const {dockNavigate}=require('./helpers/dock.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:900},reducedMotion:'reduce'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>localStorage.setItem('swu-glass:lighting-mode','"moonlight"'));
  await page.goto('http://127.0.0.1:5180/?mode=demo');
  const checkNeutral=async selector=>{
   const colors=await page.locator(selector).evaluateAll(es=>es.map(e=>({class:e.className,color:getComputedStyle(e).backgroundColor})));
   for(const {class:name,color} of colors){const values=color.match(/[\d.]+/g).map(Number);if(values.length===4&&values[3]===0)continue;assert.ok(Math.max(...values.slice(0,3))-Math.min(...values.slice(0,3))<=2,`${name} needs a neutral charcoal surface: ${color}`);}
  };
  await checkNeutral('.panel,.side-panel,.date-card,.search-glass,.small-icon');
  assert.equal(await page.locator('.subscription-inner').evaluate(e=>getComputedStyle(e).backgroundColor),'rgba(0, 0, 0, 0)','subscription content must not create a second inner slab');
  assert.equal(await page.locator('.lens:visible').count(),0,'night surfaces must not expose glass-library overlay/bottom edges');
  await page.screenshot({path:'docs/night-neutral-home.png'});
  for(const name of ['通知','订阅','来源','设置']){
   await dockNavigate(page,name);await checkNeutral('.workspace-page,.notice-center,.directory-search,.source-insight,.source-donut>div,.secondary,.page-number input');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.screenshot({path:`docs/night-neutral-${name}.png`});
  }
  await dockNavigate(page,'日程');await checkNeutral('.workspace-page,.schedule-nav,.schedule-header .month-nav>button,.workspace-segment,.weekend,.week-day-column.current-day');
  assert.ok(await page.locator('.schedule-filterbar input,.schedule-filterbar select').evaluateAll(es=>es.every(e=>getComputedStyle(e).backgroundColor==='rgba(0, 0, 0, 0)')),'compact schedule filters share their parent surface');
  await page.getByRole('button',{name:'新建日程',exact:true}).click();
  await checkNeutral('.schedule-editor,.schedule-editor .editor-info-row input,.schedule-editor .editor-info-row select');
  assert.ok(await page.locator('.schedule-editor .editor-info-row input,.schedule-editor .editor-info-row select').evaluateAll(es=>es.every(e=>getComputedStyle(e).backgroundColor==='rgba(0, 0, 0, 0)')),'editor metadata must not expose rectangular control backplates');
  await page.screenshot({path:'docs/night-neutral-schedule.png'});
  await page.getByRole('button',{name:'取消编辑',exact:true}).click();
  await dockNavigate(page,'首页');await page.locator('.notice-title').first().click();await checkNeutral('dialog[open],.dialog-actions .secondary');
  await page.getByRole('button',{name:'关闭弹窗',exact:true}).click();
  await page.setViewportSize({width:390,height:844});await checkNeutral('.side-panel,.subscription-inner');await page.screenshot({path:'docs/night-neutral-mobile.png',fullPage:true});
  await dockNavigate(page,'设置');await page.getByLabel('光线氛围',{exact:true}).selectOption('day');
  await dockNavigate(page,'首页');assert.ok(await page.locator('.lens:visible').count()>0,'daytime retains its glass treatment');
  assert.deepEqual(errors,[]);
  console.log('Night surfaces passed: neutral charcoal across all pages, no inner slabs/glass overlays, schedule/notice dialogs, mobile and daytime preserved.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
