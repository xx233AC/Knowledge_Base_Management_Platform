export type Permission = 'dashboard.view'|'org.users.manage'|'org.roles.manage'|'org.departments.manage'|'knowledge.read'|'knowledge.create'|'knowledge.update'|'knowledge.delete'|'knowledge.import'|'knowledge.permissions'|'ai.access'|'faq.review'|'faq.manage'|'gaps.manage'
export interface User {id:string;username:string;displayName:string;departmentId:string;roleIds:string[];status:'active'|'disabled';createdAt:string}
export interface Role {id:string;name:string;code:string;description:string;permissions:Permission[]}
export interface Department {id:string;name:string;parentId:string;leaderId:string;sort:number}
export interface Grant {type:'global'|'department'|'role'|'user';id?:string}
export interface Attachment {name:string;size:number;path?:string}
export interface Version {version:number;date:string;editor:string;content:string;title:string}
export interface Unit {id:string;code:string;title:string;content:string;summary:string;category:string;tags:string[];fileType:string;attachments:Attachment[];status:'draft'|'published';creatorId:string;updatedAt:string;acl:Grant[];versions:Version[];restricted?:boolean}
export interface Faq {id:string;question:string;answer:string;unitId:string;frequency:number;status:'pending_review'|'published'|'rejected';cache:boolean;reviewerId?:string;reviewedAt?:string;category:string;hits:number}
export interface Gap {id:string;question:string;samples:string[];count:number;lastAskedAt:string;status:'unresolved'|'resolved'|'ignored';unitId?:string}
export interface Citation {unitId:string;code:string;title:string;location:string}
export interface Message {id:string;role:'user'|'assistant';text:string;citations:Citation[];denied:boolean;interrupted?:boolean;cached?:boolean}
export interface Session {id:string;userId:string;title:string;updatedAt:string;messages:Message[]}
export interface AccessLog {id:string;userId:string;question:string;unitIds:string[];tokens:number;ms:number;date:string}
export interface Job {id:string;name:string;path:string;size:number;phase:number;status:'running'|'completed'|'failed'|'canceled';startedAt:string;unitId?:string;error?:string}
export interface EntityMap {users:User;roles:Role;departments:Department;units:Unit;faqs:Faq;gaps:Gap;sessions:Session;logs:AccessLog;jobs:Job}
export type Resource=keyof EntityMap
export interface Identity {user:User;permissions:Permission[];roles:Role[];department?:Department}
export interface LoginResult extends Identity {accessToken:string;expiresAt:number}
export type ChatEvent={type:'session';sessionId:string}|{type:'delta';text:string}|{type:'citations';citations:Citation[]}|{type:'denied';message?:string}|{type:'cache';hit:boolean}|{type:'done';tokens?:number;ms?:number}
export interface Service {
 login(username:string,password:string):Promise<LoginResult>
 me():Promise<Identity>
 logout():Promise<void>
 list<K extends Resource>(resource:K):Promise<EntityMap[K][]>
 getUnit(id:string):Promise<Unit>
 save<K extends Resource>(resource:K,item:Partial<EntityMap[K]> & {password?:string;gapId?:string}):Promise<EntityMap[K]>
 remove(resource:Resource,ids:string[]):Promise<void>
 resetPassword(id:string,password:string):Promise<void>
 upload(file:File,path:string,signal:AbortSignal):Promise<Job>
 job(id:string,signal?:AbortSignal):Promise<Job>
 cancelJob(id:string):Promise<void>
 dashboard(period:'7d'|'30d'|'all'):Promise<import('../domain/stats').DashboardStats>
 reviewFaq(id:string,action:'approve'|'reject',answer:string):Promise<void>
 streamChat(question:string,sessionId:string|undefined,onEvent:(event:ChatEvent)=>void,signal:AbortSignal):Promise<void>
 resetDemo():Promise<void>
}
