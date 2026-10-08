import configuration from '../../../swu-notice-monitor/data/college_competition_rules.json' with {type:'json'};

export const collegeConfiguration=configuration;
export function competitionMatchesQuery(item,query){
 const text=[item.name,item.current_name||'',item.screenshot_name||'',...(item.aliases||[]),
  ...(item.reference_rules||[]).map(x=>x.screenshot_name)].join(' ');
 return text.normalize('NFKC').toLowerCase().includes(query.normalize('NFKC').toLowerCase());
}
export function collegeReference(id,collegeId=configuration.default_college){
 const college=configuration.colleges.find(x=>x.id===collegeId);
 if(!college)throw new Error('学院不存在');
 const rules=configuration.rules.filter(x=>x.college_id===collegeId&&x.competition_id===id);
 return {college_id:collegeId,reference_rules:rules,reference_label:college.policy.label,
  recognition_note:rules.length?'':'当前学院截图未列名，分值认定待确认'};
}
export function contextualCompetition(item,collegeId){
 const context=collegeReference(item.id,collegeId);
 const rule=context.reference_rules[0];
 const level=rule?.levels.find(x=>x.name===rule.default_level);
 return {...item,...context,awards:level?.awards||[],scores:level?.scores||[],
  restriction:collegeId===configuration.default_college?item.restriction:''};
}
