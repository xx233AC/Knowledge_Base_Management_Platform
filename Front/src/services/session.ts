const key='kb.session.v1'
export interface StoredSession {accessToken:string;expiresAt:number}
export function getSession(storage:Storage=sessionStorage):StoredSession|null {try{const s=JSON.parse(storage.getItem(key)||'null');return s?.expiresAt>Date.now()&&typeof s.accessToken==='string'?s:null}catch{return null}}
export function setSession(s:StoredSession,storage:Storage=sessionStorage){storage.setItem(key,JSON.stringify(s))}
export function clearSession(storage:Storage=sessionStorage){storage.removeItem(key)}
