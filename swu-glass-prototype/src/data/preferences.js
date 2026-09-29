export function readPreference(key,fallback){try{return JSON.parse(localStorage.getItem(`swu-glass:${key}`))??fallback}catch{return fallback}}
export function writePreference(key,value){try{localStorage.setItem(`swu-glass:${key}`,JSON.stringify(value))}catch{/* Appearance remains usable when browser storage is unavailable. */}}
