import React,{useEffect,useRef,useState} from 'react';
export function Pager({page,total,size,onChange,quickJump=false}){
 const pages=Math.max(1,Math.ceil(total/size));
 const [target,setTarget]=useState(page+1),[dragging,setDragging]=useState(false);
 const targetRef=useRef(page+1);
 useEffect(()=>{targetRef.current=page+1;setTarget(page+1);setDragging(false)},[page,pages]);
 function preview(value){targetRef.current=value;setTarget(value)}
 function commit(){const parsed=Number(targetRef.current);const next=Math.min(pages,Math.max(1,Math.round(Number.isFinite(parsed)&&parsed>0?parsed:page+1)));preview(next);setDragging(false);if(next!==page+1)onChange(next-1)}
 const fraction=pages===1?0:(Number(target)-1)/(pages-1);
 return <div className={`pagination ${quickJump?'pagination-jump':''}`}>
  <span>共 {total.toLocaleString()} 条 · {page+1} / {pages} 页</span>
  {quickJump&&<div className="page-jump-control">
   <div className={`wave-slider ${dragging?'is-dragging':''}`}>
    <div className="wave-ticks" aria-hidden="true">{Array.from({length:49},(_,i)=><i key={i} className={i/48<=fraction?'passed':''} style={{'--tick-lift':dragging?Math.max(0,(1+Math.cos(Math.min(1,Math.abs(i/48-fraction)/.18)*Math.PI))/2):0}}/>)}</div>
    <input type="range" aria-label="滑动跳转页码" aria-valuetext={`第 ${target} 页，共 ${pages} 页`} min="1" max={pages} step="1" value={target||1} disabled={pages===1} onChange={e=>preview(Number(e.target.value))} onPointerDown={e=>{e.currentTarget.setPointerCapture(e.pointerId);setDragging(true)}} onPointerUp={commit} onPointerCancel={()=>{preview(page+1);setDragging(false)}} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(e.key))setDragging(true)}} onKeyUp={e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(e.key))commit()}} onBlur={commit}/>
    {dragging&&<output className="page-preview" style={{left:`${Math.max(8,Math.min(92,fraction*100))}%`}}>第 {target} 页</output>}
   </div>
   <label className="page-number">跳至<input type="number" aria-label="跳转页码" min="1" max={pages} value={target} disabled={pages===1} onChange={e=>preview(e.target.value)} onBlur={commit} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();commit()}}}/>页</label>
  </div>}
  <button disabled={page===0} onClick={()=>onChange(page-1)}>上一页</button><button disabled={page+1>=pages} onClick={()=>onChange(page+1)}>下一页</button>
 </div>;
}
