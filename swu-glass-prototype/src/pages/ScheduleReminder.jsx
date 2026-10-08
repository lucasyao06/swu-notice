import React from 'react';
import {Bell} from 'lucide-react';
import {formatReminderTime} from '../data/schedule.js';

export function ScheduleReminder({due,pending,onOpen,onAck}){
 if(!due.length)return null;
 const event=due[0];
 return <aside className="calendar-reminder" aria-label="日程提醒"><div><Bell size={16}/><strong>日程提醒</strong><span>{due.length} 项</span></div><button className="reminder-open" onClick={()=>onOpen(event)}><strong>{event.title}</strong><small>提醒时间：{formatReminderTime(event)}</small><small>日程：{event.date} · {event.time||'全天'}</small></button><button className="text-button" disabled={pending} onClick={()=>onAck(event.id)}>知道了</button></aside>;
}
