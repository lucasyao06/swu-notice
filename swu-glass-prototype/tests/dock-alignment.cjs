const {chromium}=require(process.env.PLAYWRIGHT_PATH||'playwright');
const assert=require('node:assert/strict');
const {dockNavigate}=require('./helpers/dock.cjs');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 try{
  for(const [width,height] of [[1440,900],[1280,720],[390,844]]){
   const page=await browser.newPage({viewport:{width,height}});
   await page.addInitScript(()=>localStorage.setItem('swu-glass:lighting-mode','"day"'));
   await page.goto('http://127.0.0.1:5180/?mode=demo');
   await dockNavigate(page,'日程');
   for(const theme of ['day','moonlight']){
    if(theme==='moonlight'){
     await dockNavigate(page,'设置');await page.getByLabel('光线氛围',{exact:true}).selectOption(theme);await dockNavigate(page,'日程');
    }
    await page.mouse.move(20,20);await page.waitForTimeout(280);
    const bar=page.getByRole('button',{name:'展开导航栏',exact:true}),trigger=await bar.boundingBox();
    await bar.hover();await page.waitForTimeout(300);
    const navigation=await page.locator('.dock').boundingBox();
    assert.ok(Math.abs(trigger.y+trigger.height/2-navigation.y-navigation.height/2)<1,`${width}/${theme}: pointer stays at the revealed Dock center`);
    assert.ok(navigation.y>=0&&navigation.y+navigation.height<=height,'revealed Dock stays within the viewport');
    const selected=page.getByRole('button',{name:'日程',exact:true});
    const measure=()=>selected.evaluate(button=>{
     const rect=e=>{const r=e.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,bottom:r.bottom,right:r.right}};
     return {icon:rect(button.querySelector('svg')),label:rect(button.querySelectorAll('span')[button.querySelectorAll('span').length-1]),group:rect(button.querySelector('.dock-item')),target:rect(button),nav:rect(button.parentElement)};
    });
    const before=await measure();await selected.hover();await page.waitForTimeout(240);const after=await measure();
    const iconScale=after.icon.height/before.icon.height,labelScale=after.label.height/before.label.height;
    assert.ok(Math.abs(iconScale-labelScale)<.02,`${width}/${theme}: icon and label must float together; icon scale ${iconScale}, label scale ${labelScale}`);
    assert.ok(Math.abs((after.icon.x+after.icon.width/2)-(after.target.x+after.target.width/2))<1,'icon stays centered on the stable click target');
    assert.ok(Math.abs((after.label.x+after.label.width/2)-(after.target.x+after.target.width/2))<1,'label shares the icon centerline');
    assert.ok(after.group.y>=after.nav.y+1&&after.group.bottom<=after.nav.bottom-1,'selection background stays inside Dock');
    assert.ok(after.icon.y>=after.group.y&&after.label.bottom<=after.group.bottom,'icon and label stay inside their selection background');
    assert.ok(after.icon.y>=after.nav.y+1&&after.label.bottom<=after.nav.bottom-1,'floating content stays inside Dock');
    assert.ok(after.label.y-after.icon.bottom>=3,'icon and label retain readable space');
    assert.equal(after.target.width,before.target.width,'magnification keeps click targets stable');
    if(width===1440){await page.screenshot({path:`docs/dock-alignment-${theme}.png`});await page.locator('.dock').screenshot({path:`docs/dock-alignment-detail-${theme}.png`});}
   }
   await page.close();
  }
  console.log('Dock alignment passed: icon/label move together, centered groups, safe bounds, day/night and desktop/mobile widths.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exit(1)});
