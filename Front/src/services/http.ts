import {getSession,clearSession} from './session'
export const baseUrl=(import.meta.env.VITE_API_BASE_URL||'/api').replace(/\/$/,'')
export async function request<T>(path:string,init:RequestInit={}):Promise<T>{
 const token=getSession()?.accessToken,headers=new Headers(init.headers)
 if(token)headers.set('Authorization',`Bearer ${token}`)
 if(init.body&&!(init.body instanceof FormData))headers.set('Content-Type','application/json')
 const timeout=new AbortController(),timer=setTimeout(()=>timeout.abort(),30000)
 try{
  const response=await fetch(baseUrl+path,{...init,headers,signal:init.signal||timeout.signal})
  if(response.status===401){clearSession();window.dispatchEvent(new Event('kb:unauthorized'))}
  if(!response.ok){const data=await response.json().catch(()=>({}));throw new Error(typeof data.detail==='string'?data.detail:typeof data.message==='string'?data.message:`请求失败（${response.status}），请重试`)}
  if(response.status===204)return undefined as T
  return await response.json() as T
 }catch(e){if(e instanceof TypeError)throw new Error('无法连接服务，请检查网络或稍后重试');throw e}finally{clearTimeout(timer)}
}
export const json=(value:unknown)=>JSON.stringify(value)
