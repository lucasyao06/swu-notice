export function showReadingState(notice,subscriptions){
 return notice.important===true||notice.badge==='重要'||subscriptions.sources.includes(notice.sourceId)||subscriptions.categories.includes(notice.category)||subscriptions.keywords.some(k=>k&&`${notice.title} ${notice.summary||''}`.includes(k));
}
