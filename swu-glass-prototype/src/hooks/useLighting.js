import {useEffect,useState} from 'react';
import {readPreference,writePreference} from '../data/preferences.js';
import {lightingPreference,resolveLighting,greetingAt} from '../data/lighting.js';
export function useLighting(){
 // New preference starts in automatic mode, replacing the old day-only default.
 const [preference,setPreference]=useState(()=>lightingPreference(readPreference('lighting-mode','auto')));
 const [now,setNow]=useState(()=>new Date());
 useEffect(()=>writePreference('lighting-mode',preference),[preference]);
 useEffect(()=>{
  const update=()=>setNow(new Date());
  const visible=()=>{if(document.visibilityState==='visible')update()};
  const timer=setInterval(update,15000);
  window.addEventListener('focus',update);document.addEventListener('visibilitychange',visible);
  return()=>{clearInterval(timer);window.removeEventListener('focus',update);document.removeEventListener('visibilitychange',visible)};
 },[]);
 return {preference,setPreference,phase:resolveLighting(preference,now),now,greeting:greetingAt(now)};
}
