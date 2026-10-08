async function dockNavigate(page,name){
 const handle=page.getByRole('button',{name:'展开导航栏',exact:true});
 if(await handle.getAttribute('aria-expanded')!=='true')await handle.hover();
 await page.getByRole('button',{name,exact:true}).click();
}
module.exports={dockNavigate};
