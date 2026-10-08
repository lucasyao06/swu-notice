const {dockNavigate}=require('./helpers/dock.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  const page=await browser.newPage({viewport:{width:1672,height:940},timezoneId:'Asia/Shanghai'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addInitScript(()=>{localStorage.setItem('swu-glass:lighting-mode','"day"');localStorage.setItem('swu-glass:motion','true')});
  await page.goto('http://127.0.0.1:5180/?mode=demo');
  await dockNavigate(page,'日程');
  assert.equal(await page.locator('.topbar').count(),0,'schedule page excludes the platform header');
  assert.ok((await page.locator('.workspace-page').boundingBox()).y<=16,'schedule starts at the top of the viewport');
  const dates=await page.locator('.week-day-column').evaluateAll(es=>es.map(e=>e.getAttribute('aria-label').slice(0,10)));
  for(const [title,day,start,end,category,location,notes] of [
   ['数据结构',0,'09:00','10:40','study','北区 25-0603',''],
   ['概率论与数理统计',0,'14:00','15:40','study','北区 27-0301',''],
   ['文献阅读',1,'10:00','11:30','work','北区 图书馆',''],
   ['小组讨论',1,'15:00','16:00','activity','北区 28-0402',''],
   ['实验室讨论',2,'10:00','11:00','study','学院实验室','讨论本周进展与下一步实验安排'],
   ['计算机组成原理',2,'14:00','15:40','study','北区 28-0402',''],
   ['整理研究笔记',2,'18:00','19:00','work','北区 自习室',''],
   ['阅读计划',3,'09:00','10:00','work','',''],
   ['国庆节',3,'','','activity','',''],
   ['户外活动',5,'15:00','16:30','personal','第一运动场',''],
  ]){
   await page.getByRole('button',{name:'新建日程',exact:true}).click();
   await page.getByLabel('日程标题',{exact:true}).fill(title);
   await page.getByLabel('日程分类',{exact:true}).selectOption(category);
   await page.getByLabel('地点',{exact:true}).fill(location);
   await page.getByLabel('备注',{exact:true}).fill(notes);
   await page.locator('.schedule-editor summary').click();
   await page.getByLabel('日期',{exact:true}).fill(dates[day]);
   if(start){await page.getByLabel('全天',{exact:true}).uncheck();await page.getByLabel('开始时间',{exact:true}).fill(start);await page.getByLabel('结束时间',{exact:true}).fill(end)}
   await page.getByRole('button',{name:'保存日程',exact:true}).click();
   await page.locator('.schedule-editor').waitFor({state:'hidden'});
  }
  await page.locator('.month-nav').getByRole('button',{name:'今天',exact:true}).click();
  await page.locator('.week-scroll').evaluate(e=>e.scrollTop=8*52);
  const event=page.locator('.schedule-block.timed').filter({hasText:'实验室讨论'});
  const gridBefore=await page.locator('.week-hours').boundingBox();
  const box=await event.boundingBox();await page.mouse.move(box.x+30,box.y+20);await page.waitForTimeout(240);
  assert.ok(await event.evaluate(e=>new DOMMatrix(getComputedStyle(e).transform).m42)<-1,'hover lifts schedule');
  await event.click();await page.waitForTimeout(240);
  assert.equal((await page.locator('.week-hours').boundingBox()).width,gridBefore.width,'editor must not shrink the week');
  assert.equal(await page.locator('.selected-event').count(),1);
  await page.screenshot({path:'docs/schedule-redesign-desktop.png'});
  assert.ok(await page.locator('.workspace-page').evaluate(e=>e.scrollHeight<=e.clientHeight+1),'desktop workspace does not scroll');
  await page.getByRole('button',{name:'取消编辑',exact:true}).click();
  await page.locator('.schedule-editor').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'展开导航栏',exact:true}).hover();await page.waitForTimeout(300);
  await page.screenshot({path:'docs/schedule-dock-expanded.png'});
  const dock=page.locator('.dock button').nth(2),dockBox=await dock.boundingBox();
  await page.mouse.move(dockBox.x+dockBox.width/2,dockBox.y+dockBox.height/2);await page.waitForTimeout(240);
  const scale=await dock.locator('.dock-item').evaluate(e=>new DOMMatrix(getComputedStyle(e).transform).a);
  assert.ok(scale>1.2&&scale<=1.23,'Dock icon magnifies gently');
  const neighbors=await page.locator('.dock button').evaluateAll(es=>es.map(e=>Number(getComputedStyle(e).getPropertyValue('--dock-influence'))));
  assert.ok(Math.abs(neighbors[1]-neighbors[3])<.02,'neighbors respond symmetrically');
  await page.mouse.move(30,30);await page.waitForTimeout(240);
  assert.equal(await dock.locator('.dock-item').evaluate(e=>getComputedStyle(e).transform),'matrix(1, 0, 0, 1, 0, 0)');
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.mouse.move(box.x+30,box.y+20);await page.waitForTimeout(80);
  assert.ok(await event.evaluate(e=>['none','matrix(1, 0, 0, 1, 0, 0)'].includes(getComputedStyle(e).transform)));
  await page.mouse.move(dockBox.x+dockBox.width/2,dockBox.y+20);
  assert.equal(await dock.locator('.dock-item').evaluate(e=>getComputedStyle(e).transform),'none');
  await page.emulateMedia({reducedMotion:'no-preference'});
  await dockNavigate(page,'设置');
  assert.equal(await page.locator('.topbar').count(),1,'other pages keep the platform header');
  await page.getByRole('switch',{name:'自然光效',exact:true}).click();
  await page.getByLabel('光线氛围',{exact:true}).selectOption('moonlight');
  await dockNavigate(page,'日程');
  await event.click();
  assert.equal(await page.locator('.schedule-editor').evaluate(e=>e.getAnimations().length),0);
  assert.equal(await page.locator('.schedule-editor').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(34, 34, 34)');
  await page.screenshot({path:'docs/schedule-redesign-night.png'});
  await page.setViewportSize({width:390,height:844});
  await page.waitForTimeout(150);
  const popup=await page.locator('.schedule-editor').boundingBox();
  assert.ok(popup.x>=0&&popup.x+popup.width<=390&&popup.y>=0&&popup.y+popup.height<=844);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:'docs/schedule-redesign-mobile.png'});
  assert.deepEqual(errors,[]);
  console.log('Schedule redesign passed: hover, anchored editor, Dock proximity/reset, reduced motion, motion-off, dark/mobile fit and runtime errors.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
