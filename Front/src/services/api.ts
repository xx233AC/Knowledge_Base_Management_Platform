import type {Service,Resource,EntityMap,LoginResult} from '../types/domain'
import {request,json,baseUrl} from './http'
import {getSession,clearSession} from './session'
import {consumeSSE} from '../domain/sse'
const paths:Record<Resource,string>={users:'/org/users',roles:'/org/roles',departments:'/org/departments',units:'/knowledge/units',faqs:'/settlement/faqs',gaps:'/settlement/knowledge-gaps',sessions:'/ai/sessions',logs:'/dashboard/logs',jobs:'/knowledge/import/jobs'}
export const api:Service={
 async login(username,password){const r=await request<any>('/auth/login',{method:'POST',body:json({username,password})});return {user:r.user_info,roles:r.roles,permissions:r.permissions,accessToken:r.access_token,expiresAt:Date.now()+(r.expires_in||3600)*1000} as LoginResult},
 me:()=>request('/auth/me'),
 async logout(){try{await request('/auth/logout',{method:'POST'})}finally{clearSession()}},
 async list<K extends Resource>(resource:K){const rows:EntityMap[K][]=[];let page=1;while(page<=100){const result=await request<{items:EntityMap[K][];total:number}>(paths[resource]+`?page=${page}&page_size=100`);rows.push(...result.items);if(rows.length>=result.total)return rows;page++}throw new Error('数据量过大，请后端提供筛选或分页后再加载')},
 getUnit:id=>request(`/knowledge/units/${encodeURIComponent(id)}`),
 async save(resource,item){
  const id=item.id,aclOnly=resource==='units'&&id&&Object.keys(item).every(k=>['id','acl'].includes(k))
  if(aclOnly)return request(paths.units+`/${encodeURIComponent(id)}/permissions`,{method:'POST',body:json({permissions:(item as any).acl})})
  if(resource==='roles'&&id){const {permissions,...metadata}=item as Partial<EntityMap['roles']>;await request(paths.roles+`/${encodeURIComponent(id)}`,{method:'PUT',body:json(metadata)});return request(paths.roles+`/${encodeURIComponent(id)}/permissions`,{method:'POST',body:json({permissions})})}
  return request(paths[resource]+(id?`/${encodeURIComponent(id)}`:''),{method:id?'PUT':'POST',body:json(item)})
 },
 remove:(resource,ids)=>request(paths[resource],{method:'DELETE',body:json({ids})}),
 resetPassword:(id,password)=>request(`/org/users/${encodeURIComponent(id)}/reset-password`,{method:'POST',body:json({password})}),
 async upload(file,path,signal){const form=new FormData();form.append('files',file);form.append('relative_paths',path);const result=await request<{jobs:EntityMap['jobs'][]}>('/knowledge/import',{method:'POST',body:form,signal});if(!result.jobs[0])throw new Error('服务未返回导入任务');return result.jobs[0]},
 job:(id,signal)=>request(`/knowledge/import/jobs/${encodeURIComponent(id)}`,{signal}),
 cancelJob:id=>request(`/knowledge/import/jobs/${encodeURIComponent(id)}/cancel`,{method:'POST'}),
 dashboard:async period=>{const q=`?period=${period}`;const [metrics,questions,hotUnits,trend,bins]=await Promise.all([request<any>('/dashboard/metrics'+q),request<any>('/dashboard/rankings/questions'+q),request<any>('/dashboard/rankings/units'+q),request<any>('/dashboard/stats/tokens'+q),request<any>('/dashboard/stats/latency'+q)]);return {...metrics,questions,hotUnits,trend,bins}},
 reviewFaq:(id,action,answer)=>request(`/settlement/faqs/${encodeURIComponent(id)}/review`,{method:'POST',body:json({action,edited_answer:answer})}),
 async streamChat(question,sessionId,onEvent,signal){
  const response=await fetch(baseUrl+'/ai/chat/stream',{method:'POST',headers:{'Content-Type':'application/json','Accept':'text/event-stream',Authorization:`Bearer ${getSession()?.accessToken||''}`},body:json({question,session_id:sessionId}),signal})
  if(response.status===401){clearSession();window.dispatchEvent(new Event('kb:unauthorized'))}
  if(!response.ok){const e=await response.json().catch(()=>({}));throw new Error(typeof e.detail==='string'?e.detail:'AI 服务请求失败，请重试')}
  if(!response.body||!response.headers.get('content-type')?.includes('text/event-stream'))throw new Error('服务未返回流式回答')
  await consumeSSE(response.body,onEvent,signal)
 },
 async resetDemo(){throw new Error('接口模式不支持重置演示数据')},
}
