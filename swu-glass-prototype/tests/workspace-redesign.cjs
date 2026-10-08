const {dockNavigate}=require('./helpers/dock.cjs');
const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});try{
 const page=await browser.newPage({viewport:{width:1280,height:720},reducedMotion:'reduce'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5180/?mode=demo');await page.locator('.loading-status').waitFor({state:'hidden'});
 await dockNavigate(page,'订阅');
 assert.equal(await page.locator('.followed-unit').count(),4);
 assert.ok((await page.locator('.followed-unit input').evaluateAll(nodes=>nodes.every(n=>n.checked))));
 await page.getByRole('button',{name:'添加单位',exact:true}).click();
 await page.getByRole('textbox',{name:'查找订阅单位'}).fill('图书馆');
 assert.equal(await page.locator('.followed-unit').count(),1);
 const checkbox=page.locator('.followed-unit input');const before=await checkbox.isChecked();await checkbox.click();
 await page.getByText('有未保存的修改',{exact:true}).waitFor();
 await page.getByRole('button',{name:'重置修改',exact:true}).click();assert.equal(await checkbox.isChecked(),before);
 await page.getByRole('textbox',{name:'订阅关键词'}).fill('测试关键词、日历');
 await page.getByRole('button',{name:'保存订阅',exact:true}).click();await page.getByRole('status').filter({hasText:'订阅已保存'}).waitFor();
 await page.getByText('偏好已同步',{exact:true}).waitFor();
 await dockNavigate(page,'来源');
 const category=page.getByRole('navigation',{name:'来源类型'}).getByRole('button').nth(1);await category.click();
 assert.equal(await category.getAttribute('aria-pressed'),'true');
 const type=await category.locator('span').innerText();
 assert.ok((await page.locator('.source-unit small').allTextContents()).every(t=>t===type.trim()));
 await page.getByRole('textbox',{name:'查找来源'}).fill('没有这个单位');
 await page.getByText('没有符合条件的来源',{exact:true}).waitFor();await page.getByRole('button',{name:'清空筛选',exact:true}).click();
 assert.equal(await page.locator('.source-table-row').count(),5);
 const statuses=await page.getByRole('combobox',{name:'采集状态'}).locator('option').allTextContents();
 if(statuses.length>1){await page.getByRole('combobox',{name:'采集状态'}).selectOption(statuses[1]);assert.ok((await page.locator('.collection-state').allTextContents()).every(s=>s===statuses[1]))}
 for(const label of ['订阅','来源']){await page.setViewportSize({width:390,height:844});await dockNavigate(page,label);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${label}: mobile overflow`)}
 assert.deepEqual(errors,[]);console.log('Workspace redesign passed: selected units, add/search/reset, save, category/status/empty filters, mobile width.');
 }finally{await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
