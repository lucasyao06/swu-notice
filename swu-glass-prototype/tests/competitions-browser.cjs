const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
async function wait(url){for(let i=0;i<100;i++){try{if((await fetch(url)).ok)return}catch{}await new Promise(r=>setTimeout(r,100))}throw new Error('Server not ready: '+url)}
(async()=>{
 const api=spawn(process.env.PYTHON_PATH||'python',['tests/competition_fixture.py'],{cwd:root,env:{...process.env,SWU_ALLOWED_ORIGINS:'http://127.0.0.1:5182'},stdio:'ignore'});
 const vite=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port','5182','--strictPort'],{cwd:root,env:{...process.env,SWU_API_TARGET:'http://127.0.0.1:8877'},stdio:'ignore'});
 let browser;
 try{
  await wait('http://127.0.0.1:8877/api/health');await wait('http://127.0.0.1:5182/');
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const idle=async()=>{await page.waitForTimeout(150);await page.locator('.competition-loading').waitFor({state:'hidden'});assert.equal(await page.locator('.competition-error').count(),0,await page.locator('.competition-error').allTextContents().then(x=>x.join(' ')))};
  await page.goto('http://127.0.0.1:5182/');await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();
  assert.equal(await page.locator('.competition-card').count(),12);
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('美国大学生');await idle();assert.equal(await page.locator('.competition-card').count(),1);
  await page.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();assert.equal(await page.locator('.competition-dialog th').allTextContents().then(x=>x.join(',')),'O,F,M,H,S');
  await page.keyboard.press('Escape');await page.locator('.competition-dialog[open]').waitFor({state:'hidden'});
  await page.getByRole('button',{name:'官网通知',exact:true}).click();await idle();assert.equal(await page.locator('.competition-notice-list article').count(),10);
  await page.getByRole('button',{name:'下一页',exact:true}).click();await idle();assert.equal(await page.locator('.competition-notice-list article').count(),3);
  await page.getByRole('textbox',{name:'搜索赛事通知'}).fill('通知13');await idle();assert.equal(await page.locator('.competition-notice-list article').count(),1);
  await page.locator('.competition-notice-title').click();await page.getByRole('button',{name:'收藏通知',exact:true}).click();await idle();
  await page.getByRole('button',{name:'标记已读',exact:true}).click();await idle();await page.keyboard.press('Escape');
  const campusUnread=(await(await fetch('http://127.0.0.1:8877/api/messages?mode=live')).json()).unread;
  await page.getByRole('button',{name:'消息中心',exact:true}).click();await idle();assert.equal(await page.locator('.competition-message-list article').count(),10);
  await page.getByRole('button',{name:'全部标记已读'}).click();await idle();assert.equal((await(await fetch('http://127.0.0.1:8877/api/competition/messages')).json()).unread,0);
  assert.equal((await(await fetch('http://127.0.0.1:8877/api/messages?mode=live')).json()).unread,campusUnread);
  await page.getByRole('button',{name:'赛事目录',exact:true}).click();await idle();await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('CCPC');await idle();await page.getByRole('button',{name:'关注赛事',exact:true}).click();await idle();
  await page.reload();await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();await page.getByRole('button',{name:'我的关注',exact:true}).click();await idle();assert.equal(await page.locator('.competition-card').count(),2);
  await page.getByRole('button',{name:'官网通知',exact:true}).click();await idle();await page.getByRole('button',{name:'我的收藏',exact:true}).click();await idle();assert.equal(await page.locator('.competition-notice-list article').count(),1);
  await page.route('**/api/competition/notices?**',r=>r.fulfill({status:503,contentType:'application/json',body:'{"error":"赛事测试离线"}'}));await page.getByRole('button',{name:'刷新',exact:true}).click();await page.getByRole('alert').filter({hasText:'赛事测试离线'}).waitFor();await page.unroute('**/api/competition/notices?**');await page.getByRole('button',{name:'重试',exact:true}).click();await idle();
  const college=page.getByRole('combobox',{name:'选择学院',exact:true});
  await college.selectOption('law');await idle();
  assert.equal(await page.locator('.competition-notice-list article').count(),1); // favorite cumcm survives outside law
  assert.match(await page.locator('.competition-notice-list').innerText(),/当前学院的赛事认定待确认/);
  await page.locator('.competition-notice-title').click();await page.locator('.competition-dialog[open]').waitFor();
  assert.equal(await page.locator('.competition-dialog table').count(),0);await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'全部',exact:true}).click();await idle();assert.equal(await page.locator('.competition-notice-list article').count(),2);
  await page.getByRole('button',{name:'赛事目录',exact:true}).click();await idle();assert.match(await page.locator('.competition-toolbar').innerText(),/17 场赛事/);
  await page.getByRole('combobox',{name:'规则类别',exact:true}).selectOption('创新创业');await idle();assert.equal(await page.locator('.competition-card').count(),2);
  const business=page.locator('.competition-card').filter({hasText:'中国大学生创业计划'});
  await business.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();assert.match(await page.locator('.competition-dialog').innerText(),/25分.*20分/);await page.keyboard.press('Escape');
  await page.getByRole('combobox',{name:'规则类别',exact:true}).selectOption('专业技能');await idle();assert.equal(await page.locator('.competition-card').count(),12);
  const fractional=page.locator('.competition-card').filter({hasText:'至立'});assert.deepEqual(await fractional.locator('td').allTextContents(),['2.5','2','1.5']);
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('天欣杯');await idle();await page.getByRole('button',{name:'关注赛事',exact:true}).click();await idle();
  await page.getByRole('button',{name:'我的关注',exact:true}).click();await idle();assert.equal(await page.locator('.competition-card').count(),3);assert.equal(await page.locator('.competition-card').filter({hasText:'当前学院的赛事认定待确认'}).count(),2);
  await page.getByRole('button',{name:'赛事目录',exact:true}).click();await idle();await page.getByRole('combobox',{name:'赛事范围',exact:true}).selectOption('all');await idle();assert.match(await page.locator('.competition-toolbar').innerText(),/73 场赛事/);
  await page.getByRole('combobox',{name:'赛事范围',exact:true}).selectOption('college');await page.reload();await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();assert.equal(await college.inputValue(),'law');
  await page.route('**/api/competition/catalog?**',async route=>{if(new URL(route.request().url()).searchParams.get('college')==='cis'){const response=await route.fetch();await new Promise(r=>setTimeout(r,400));try{await route.fulfill({response})}catch{}}else await route.continue()});
  await college.selectOption('cis');await page.waitForTimeout(50);await college.selectOption('law');await idle();await page.waitForTimeout(500);
  assert.match(await page.locator('.competition-toolbar').innerText(),/17 场赛事/);assert.equal(await page.locator('.competition-card').filter({hasText:'数学建模'}).count(),0);assert.equal(await page.locator('.competition-dialog[open]').count(),0);
  await page.unroute('**/api/competition/catalog?**');
  await college.selectOption('engineering');await idle();
  assert.match(await page.locator('.competition-toolbar').innerText(),/21 场赛事/);
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('美国');await idle();
  await page.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();
  assert.deepEqual(await page.locator('.competition-dialog td').allTextContents(),['30','25','15','10','2']);
  await page.keyboard.press('Escape');await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('机器人及人工智能');await idle();
  await page.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();
  assert.match(await page.locator('.competition-dialog').innerText(),/机器人省级分值待学院确认/);
  assert.equal(await page.locator('.competition-dialog table').count(),1);await page.keyboard.press('Escape');
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('');
  await page.getByRole('combobox',{name:'规则类别',exact:true}).selectOption('创新创业');await idle();
  assert.equal(await page.locator('.competition-card').count(),2);
  const unassociated=page.locator('.competition-unassociated-rule');await unassociated.locator('summary').click();
  assert.match(await unassociated.innerText(),/暂不套用到课外学术科技作品赛或创业计划赛/);assert.equal(await unassociated.locator('table').count(),3);
  const engineeringHanhong=page.locator('.competition-card').filter({hasText:'含弘杯'});
  assert.deepEqual(await engineeringHanhong.locator('td').allTextContents(),['5','3.5','2.5','1']);
  await engineeringHanhong.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();
  assert.match(await page.locator('.competition-dialog').innerText(),/2025年9月至2026年8月/);
  await college.selectOption('law');await idle();assert.equal(await page.locator('.competition-dialog[open]').count(),0);
  await college.selectOption('engineering');await idle();await page.reload();
  await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();assert.equal(await college.inputValue(),'engineering');
  await page.route('**/api/competition/catalog?**',async route=>{if(new URL(route.request().url()).searchParams.get('college')==='law'){const response=await route.fetch();await new Promise(r=>setTimeout(r,400));try{await route.fulfill({response})}catch{}}else await route.continue()});
  await college.selectOption('law');await page.waitForTimeout(50);await college.selectOption('engineering');await idle();await page.waitForTimeout(500);
  assert.match(await page.locator('.competition-toolbar').innerText(),/21 场赛事/);await page.unroute('**/api/competition/catalog?**');
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));if(width!==320)await page.screenshot({path:path.join(root,'docs',`competition-engineering-${width}.png`),fullPage:true})}
  await college.selectOption('law');await idle();
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));if(width===1440||width===390)await page.screenshot({path:path.join(root,'docs',`competition-law-${width}.png`),fullPage:true})}
  await college.selectOption('cis');await idle();await page.setViewportSize({width:1440,height:1000});
  assert.match(await page.locator('.competition-toolbar').innerText(),/45 场赛事/);
  await page.locator('.competition-policy-notes summary').click();
  assert.match(await page.locator('.competition-policy-notes').innerText(),/4人及以上.*第4—5名按50%/);
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('课外学术科技');await idle();
  await page.locator('.competition-card').filter({hasText:'挑战杯'}).locator('.competition-title').click();
  await page.locator('.competition-dialog[open]').waitFor();
  assert.deepEqual(await page.locator('.competition-dialog td').allTextContents(),['30','25','20','15','4','15','12.5','10','7.5','2','7.5','6.25','5','3.75','0']);
  assert.doesNotMatch(await page.locator('.competition-dialog').innerText(),/截图底部|共享单用户|建立更新基线|来源与解析|用户确认|第\d+条|Traceback|SSL|HTTP Error/);
  for(const width of [1440,390,320]){await page.setViewportSize({width,height:900});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  await page.keyboard.press('Escape');await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('含弘');await idle();
  const cisHanhong=page.locator('.competition-card');assert.deepEqual(await cisHanhong.locator('td').allTextContents(),['未列明','未列明','未列明','未列明','未列明']);
  await cisHanhong.locator('.competition-title').click();await page.locator('.competition-dialog[open]').waitFor();
  assert.match(await page.locator('.competition-dialog').innerText(),/具体奖项分值待学院确认/);await page.keyboard.press('Escape');
  await page.getByRole('textbox',{name:'搜索赛事',exact:true}).fill('');await idle();

  await page.getByRole('combobox',{name:'数据模式',exact:true}).selectOption('demo');await idle();await page.getByRole('button',{name:'官网通知',exact:true}).click();await idle();assert.equal(await page.locator('.competition-notice-list article').count(),4);
  await page.getByRole('button',{name:'赛事目录',exact:true}).click();await idle();
  await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('combobox',{name:'光线氛围'}).selectOption('morning');await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();assert.equal(await page.locator('.light-morning').count(),1);await college.selectOption('law');await idle();assert.match(await page.locator('.competition-toolbar').innerText(),/17 场赛事/);
  for(const width of [1440,390,320]){
   await page.setViewportSize({width,height:900});await page.waitForTimeout(150);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'horizontal overflow at '+width);
   if(width===1440||width===390)await page.screenshot({path:path.join(root,'docs',`competition-${width}.png`),fullPage:true});
  }
  await page.getByRole('button',{name:'设置',exact:true}).click();await page.getByRole('combobox',{name:'光线氛围'}).selectOption('moonlight');await page.getByRole('button',{name:'赛事',exact:true}).click();await idle();assert.equal(await page.locator('.light-moonlight').count(),1);
  await page.screenshot({path:path.join(root,'docs','competition-night.png'),fullPage:true});assert.deepEqual(errors,[]);
  console.log('Competition browser checks passed: college switching and refresh memory, shared scores and fractional points, 73-item view/categories, delayed-request isolation, global follow/favorite/read/messages, pagination/search, original flows, errors/demo, 1440/390/320px, law day/night.');
 }finally{await browser?.close();vite.kill();api.kill()}
})().catch(e=>{console.error(e);process.exitCode=1});
