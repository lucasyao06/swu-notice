import React from 'react';
import {LIGHTING_LABELS} from '../data/lighting.js';
export function AmbientLight({phase}){return <div className="ambient-light" aria-hidden="true">{Object.keys(LIGHTING_LABELS).map(mode=><div key={mode} className={`ambient-layer ambient-${mode} ${phase===mode?'is-active':''}`}><div className="ambient-wash"/><div className="ambient-rays"/></div>)}</div>}
