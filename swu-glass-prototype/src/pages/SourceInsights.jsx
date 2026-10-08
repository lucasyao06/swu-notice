import React from 'react';
const COLORS={'正常':'#57ae9b','延迟':'#d6aa62','失败':'#d5808b','未接入':'#a0aec0'};
export function SourceInsights({sites,subscriptions}){
 const total=sites.length,followed=sites.filter(s=>subscriptions.sources.includes(s.id)).length;
 const groups=Object.entries(sites.reduce((counts,s)=>({...counts,[s.status]:(counts[s.status]||0)+1}),{}));
 let end=0;const stops=groups.map(([label,count])=>{const start=end;end+=count/total*100;return `${COLORS[label]||'#a0aec0'} ${start}% ${end}%`});
 const percent=total?Math.round(followed/total*100):0;
 return <aside className="source-insights" aria-label="来源数据概览">
  <section className="source-insight"><header><h3>采集状态</h3><span>全部来源</span></header><div className="source-donut" role="img" aria-label={groups.map(([label,count])=>`${label} ${count} 个`).join('，')||'暂无来源'} style={{background:total?`conic-gradient(${stops.join(',')})`:'#a0aec033'}}><div><strong>{total}</strong><span>来源总数</span></div></div><div className="source-legend">{groups.map(([label,count])=><span key={label}><i style={{background:COLORS[label]||'#a0aec0'}}/>{label}<b>{count}</b></span>)}</div></section>
  <section className="source-insight subscription-insight"><header><h3>我的关注</h3><span>来源覆盖</span></header><div className="follow-metric"><strong>{followed}</strong><span>个来源已关注</span></div><div className="follow-meter" role="meter" aria-label="已关注来源占比" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><i style={{width:`${percent}%`}}/></div><div className="follow-ratio"><span>关注占比</span><strong>{percent}%</strong></div><div className="insight-bottom"><span>未关注</span><b>{total-followed} 个</b></div></section>
 </aside>;
}
