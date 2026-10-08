const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const {spawn}=require('node:child_process');
const path=require('node:path');
const assert=require('node:assert/strict');
const {dockNavigate}=require('./helpers/dock.cjs');
const root=path.resolve(__dirname,'..');
async function wait(url){
 for(let i=0;i<100;i++){
  try{if((await fetch(url)).ok)return}catch{}
  await new Promise(resolve=>setTimeout(resolve,100));
 }
 throw Error(`Server did not start: ${url}`);
}
async function api(route,body){
 const response=await fetch(`http://127.0.0.1:8876/api/${route}`,body?{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{});
 assert.ok(response.ok,`Fixture API ${route}: ${response.status}`);
 return response.json();
}
(async()=>{
 const backend=spawn('python3',['tests/fixture_backend.py',path.resolve(root,'../swu-notice-monitor')],{cwd:root,stdio:'ignore'});
 const vite=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5181','--strictPort'],{cwd:root,env:{...process.env,SWU_API_TARGET:'http://127.0.0.1:8876'},stdio:'ignore'});
 let browser;
 try{
  await wait('http://127.0.0.1:8876/api/health');await wait('http://127.0.0.1:5181');
  const list=await api('calendar/lists',{name:'课程清单',color:'blue'});
  await api('calendar/events',{title:'上午课程',date:'2026-10-06',time:'09:00',end_time:'10:00',category:'study'});
  await api('calendar/events',{title:'下午讨论',date:'2026-10-06',time:'14:00',end_time:'15:00',category:'work',list_id:list.id});
  await api('calendar/events',{title:'待安排任务',date:''});
  const before=await api('calendar/events');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
  const page=await browser.newPage({viewport:{width:1440,height:900},timezoneId:'Asia/Shanghai',reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.clock.install({time:new Date('2026-10-03T12:00:00+08:00')});
  await page.goto('http://127.0.0.1:5181');await page.locator('article').first().waitFor();
  await dockNavigate(page,'日程');
  const nav=page.getByRole('complementary',{name:'日程导航'});
  const tabs=page.locator('[aria-label="日程视图切换"]');
  await page.getByRole('button',{name:'下一周',exact:true}).click();
  await page.locator('.schedule-block').filter({hasText:'下午讨论'}).waitFor();
  await page.locator('.week-scroll').evaluate(element=>element.scrollTop=13*52);
  const scrollTop=await page.locator('.week-scroll').evaluate(element=>element.scrollTop);
  const dates=await page.locator('.week-heading time').allTextContents();
  for(const scope of ['未安排','今天','最近 7 天','逾期','收集箱']){
   await nav.getByRole('button',{name:scope,exact:true}).click();
   await nav.getByRole('button',{name:'全部日程',exact:true}).click();
   assert.equal(await page.locator('.schedule-week').count(),1,`Returning from ${scope} must restore the week view`);
   assert.deepEqual(await page.locator('.week-heading time').allTextContents(),dates,'The selected week must remain unchanged');
   assert.equal(await page.locator('.week-scroll').evaluate(element=>element.scrollTop),scrollTop,'The visible time range must remain unchanged');
   assert.equal(await page.locator('.schedule-block.timed').count(),2,'Scheduled events must remain displayed');
  }
  await tabs.getByRole('button',{name:'月',exact:true}).click();
  await nav.getByRole('button',{name:'未安排',exact:true}).click();
  await nav.getByRole('button',{name:'全部日程',exact:true}).click();
  assert.equal(await page.locator('.month-grid').count(),1,'Returning must restore a chosen month view');
  await tabs.getByRole('button',{name:'清单',exact:true}).click();
  await nav.getByRole('button',{name:'未安排',exact:true}).click();
  assert.equal(await page.locator('.schedule-list-row').count(),1,'Unscheduled must show only undated tasks');
  await nav.getByRole('button',{name:'全部日程',exact:true}).click();
  assert.equal(await page.locator('.schedule-list-row').count(),3,'All events must restore a chosen list view');
  await page.locator('.custom-list-nav').getByRole('button',{name:/^课程清单/}).click();
  assert.equal(await page.locator('.schedule-list-row').count(),1,'A custom list must filter its tasks');
  await nav.getByRole('button',{name:'全部日程',exact:true}).click();
  assert.equal(await page.locator('.schedule-list-row').count(),3,'Returning from a custom list must clear its scope');
  assert.deepEqual(await api('calendar/events'),before,'Navigation must not modify persisted events');
  assert.deepEqual(errors,[]);
  console.log('Schedule navigation passed: week/month/list restoration, selected dates, scroll position, scopes, custom lists and unchanged persisted data.');
 }finally{
  if(browser)await browser.close();backend.kill('SIGTERM');vite.kill('SIGTERM');
 }
})().catch(error=>{console.error(error);process.exit(1)});
