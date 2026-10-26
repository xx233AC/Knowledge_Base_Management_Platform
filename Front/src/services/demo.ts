import {createSeed,type Database} from '../demo/seed'
import {canRead} from '../domain/permissions'
import {aggregate} from '../domain/stats'
import {getSession,clearSession} from './session'
import type {Service,Resource,EntityMap,Identity,Permission,Unit,Session,ChatEvent,Grant} from '../types/domain'

const storageKey='kb.demo.v1'
const clone=<T>(value:T):T=>JSON.parse(JSON.stringify(value))
const uid=()=>crypto.randomUUID()
const now=()=>new Date().toISOString()
function wait(ms:number,signal?:AbortSignal){return new Promise<void>((resolve,reject)=>{const abort=()=>{clearTimeout(timer);reject(new DOMException('已停止','AbortError'))};const timer=setTimeout(()=>{signal?.removeEventListener('abort',abort);resolve()},ms);if(signal?.aborted)abort();else signal?.addEventListener('abort',abort,{once:true})})}

export function createDemo(storage:Storage,sessionStorage:Storage):Service {
 function read():Database {const raw=storage.getItem(storageKey);if(raw){try{const db=JSON.parse(raw);if(db.schema===1)return db}catch{throw new Error('本地演示数据无法读取，请在个人中心重置演示数据')}}const db=createSeed();write(db);return db}
 function write(db:Database){try{storage.setItem(storageKey,JSON.stringify(db))}catch{throw new Error('本地存储空间不足，保存失败；请导出所需文本后重置演示数据')}}
 function identity(db:Database):Identity {const token=getSession(sessionStorage)?.accessToken;const user=db.users.find(u=>token===`demo:${u.id}`);if(!user||user.status!=='active')throw new Error('登录已失效，请重新登录');const roles=db.roles.filter(r=>user.roleIds.includes(r.id));return {user,roles,department:db.departments.find(d=>d.id===user.departmentId),permissions:[...new Set(roles.flatMap(r=>r.permissions))]}}
 function require(db:Database,permission:Permission){const me=identity(db);if(!me.permissions.includes(permission))throw new Error('你没有执行此操作的权限');return me}
 function visible(db:Database,unit:Unit):boolean {return canRead(identity(db).user,unit)}
 function safeUnit(db:Database,unit:Unit):Unit {if(visible(db,unit))return clone(unit);return {...clone(unit),title:'未授权知识单元',content:'',summary:'',attachments:[],tags:[],versions:[],restricted:true}}
 function validateAcl(db:Database,acl:Grant[]){for(const g of acl){const rows=g.type==='department'?db.departments:g.type==='role'?db.roles:g.type==='user'?db.users:null;if(g.type!=='global'&&(!rows||!rows.some(x=>x.id===g.id)))throw new Error('授权对象不存在，请重新选择')}}
 function protectAdmin(db:Database){if(!db.users.some(u=>u.status==='active'&&db.roles.some(r=>u.roleIds.includes(r.id)&&r.permissions.includes('org.users.manage')&&r.permissions.includes('org.roles.manage'))))throw new Error('必须保留至少一位可管理用户与角色的启用管理员')}
 const resourcePermissions:Partial<Record<Resource,Permission>>={users:'org.users.manage',roles:'org.roles.manage',departments:'org.departments.manage',faqs:'faq.review',gaps:'gaps.manage',logs:'dashboard.view',jobs:'knowledge.import',sessions:'ai.access',units:'knowledge.read'}
 function safeSession(db:Database,s:Session):Session {return {...clone(s),messages:s.messages.map(m=>{if(m.role==='user')return clone(m);const readable=m.citations.every(c=>{const u=db.units.find(u=>u.id===c.unitId);return u?.status==='published'&&visible(db,u)});return readable?clone(m):{...clone(m),text:'相关知识的访问权限或发布状态已变更，此条回答暂不可查看。',citations:[],denied:true}})}}
 const service:Service={
  async login(username,password){const db=read(),user=db.users.find(u=>u.username===username&&u.status==='active');if(!user||db.passwords[user.id]!==password)throw new Error('用户名或密码错误，或账号已停用');const roles=db.roles.filter(r=>user.roleIds.includes(r.id));return {user:clone(user),roles:clone(roles),permissions:[...new Set(roles.flatMap(r=>r.permissions))],accessToken:`demo:${user.id}`,expiresAt:Date.now()+8*3600000}},
  async me(){return clone(identity(read()))},
  async logout(){clearSession(sessionStorage)},
  async list<K extends Resource>(resource:K):Promise<EntityMap[K][]>{
   const db=read(),me=identity(db),p=resourcePermissions[resource]!
   const aclPicker=['users','roles','departments'].includes(resource)&&me.permissions.includes('knowledge.permissions')||['roles','departments'].includes(resource)&&me.permissions.includes('org.users.manage')||resource==='users'&&me.permissions.includes('org.departments.manage')
   if(!me.permissions.includes(p)&&!aclPicker&&!(resource==='units'&&me.permissions.includes('dashboard.view'))&&!(resource==='faqs'&&me.permissions.includes('faq.manage')))throw new Error('无权访问该模块')
   let rows:any[]=db[resource]
   if(resource==='units')rows=db.units.map(u=>safeUnit(db,u))
   if(resource==='sessions')rows=db.sessions.filter(s=>s.userId===me.user.id).map(s=>safeSession(db,s))
   if(resource==='users'&&aclPicker&&!me.permissions.includes(p))rows=db.users.filter(u=>me.permissions.includes('org.departments.manage')||u.status==='active').map(u=>({...u,username:me.permissions.includes('org.departments.manage')?u.username:'',roleIds:[]}))
   if(resource==='roles'&&aclPicker&&!me.permissions.includes(p))rows=db.roles.map(r=>({...r,permissions:[]}))
   if(resource==='faqs')rows=db.faqs.map(f=>{const u=db.units.find(u=>u.id===f.unitId);return u?.status==='published'&&visible(db,u)?f:{...f,question:'关联资料未授权、未发布或已删除',answer:'',cache:false}})
   return clone(rows) as EntityMap[K][]
  },
  async getUnit(id){const db=read();require(db,'knowledge.read');const unit=db.units.find(u=>u.id===id);if(!unit)throw new Error('知识不存在或已删除');if(!visible(db,unit))throw new Error('此知识当前未获授权，请联系知识管理员');return clone(unit)},
  async save<K extends Resource>(resource:K,input:Partial<EntityMap[K]> & {password?:string;gapId?:string}):Promise<EntityMap[K]>{
   const db=read(),me=identity(db),item:any=clone(input),rows:any[]=db[resource],existing=rows.find(x=>x.id===item.id),id=existing?.id||uid()
   delete item.restricted
   if(resource==='units'){
    const aclOnly=existing&&Object.keys(item).every(k=>['id','acl'].includes(k))
    require(db,aclOnly?'knowledge.permissions':existing?'knowledge.update':'knowledge.create')
    if(existing&&!aclOnly&&!visible(db,existing))throw new Error('知识内容未授权，不能编辑')
    if(item.acl){if(!me.permissions.includes('knowledge.permissions'))throw new Error('没有配置数据授权的权限');validateAcl(db,item.acl)}
    if(!aclOnly&&(!item.title?.trim()||!item.content?.trim()))throw new Error('请填写知识标题与正文')
    const gap=item.gapId?db.gaps.find(g=>g.id===item.gapId):null
    if(gap)require(db,'gaps.manage')
    const unit:Unit={id,code:`KB-${String(db.units.reduce((m,u)=>Math.max(m,Number(u.code.slice(3))||0),0)+1).padStart(3,'0')}`,title:'',content:'',summary:'',category:'未分类',tags:[],fileType:'Markdown',attachments:[],status:'draft',creatorId:me.user.id,acl:[],versions:[],updatedAt:now(),...existing,...item}
    delete (unit as any).gapId
    unit.updatedAt=now();unit.title=unit.title.trim();unit.summary=unit.content.replace(/[#*\n]/g,' ').slice(0,120)
    if(!aclOnly)unit.versions=[...(existing?.versions||[]),{version:(existing?.versions.length||0)+1,date:now(),editor:me.user.displayName,content:unit.content,title:unit.title}]
    if(existing)rows.splice(rows.indexOf(existing),1,unit);else rows.unshift(unit)
    if(gap){gap.status='resolved';gap.unitId=id}
    write(db);return safeUnit(db,unit) as EntityMap[K]
   }
   if(resource==='users'){
    require(db,'org.users.manage');const u={id,username:'',displayName:'',departmentId:'',roleIds:[],status:'active',createdAt:now(),...existing,...item};delete u.password
    if(!u.username.trim()||!u.displayName.trim()||!db.departments.some(d=>d.id===u.departmentId)||!u.roleIds.length||u.roleIds.some((r:string)=>!db.roles.some(x=>x.id===r)))throw new Error('请填写完整用户信息并分配有效部门和角色')
    if(db.users.some(x=>x.id!==id&&x.username===u.username))throw new Error('用户名已存在')
    if(!existing&&(!item.password||item.password.length<8))throw new Error('初始密码至少 8 位')
    if(existing)rows.splice(rows.indexOf(existing),1,u);else{rows.push(u);db.passwords[id]=item.password}
    protectAdmin(db);db.departments.forEach(d=>{if(d.leaderId===u.id&&(u.status!=='active'||u.departmentId!==d.id))d.leaderId=''});write(db);return clone(u)
   }
   if(resource==='roles'){
    require(db,'org.roles.manage');const r={id,name:'',code:'',description:'',permissions:[],...existing,...item}
    if(!r.name.trim()||!r.code.trim())throw new Error('请填写角色名称与编码')
    if(db.roles.some(x=>x.id!==id&&x.code===r.code))throw new Error('角色编码已存在')
    if(existing)rows.splice(rows.indexOf(existing),1,r);else rows.push(r)
    protectAdmin(db);write(db);return clone(r)
   }
   if(resource==='departments'){
    require(db,'org.departments.manage');const d={id,name:'',parentId:'',leaderId:'',sort:0,...existing,...item}
    if(!d.name.trim())throw new Error('请填写部门名称')
    if(d.leaderId&&!db.users.some(u=>u.id===d.leaderId&&u.departmentId===id&&u.status==='active'))throw new Error('负责人须为本部门启用成员')
    const seen=new Set([id]);let parent=d.parentId
    while(parent){if(seen.has(parent))throw new Error('部门不能归属自身或下级部门');seen.add(parent);const p=db.departments.find(x=>x.id===parent);if(!p)throw new Error('上级部门不存在');parent=p.parentId}
    if(existing)rows.splice(rows.indexOf(existing),1,d);else rows.push(d)
    write(db);return clone(d)
   }
   if(resource==='faqs'){
    require(db,'faq.manage');if(!existing)throw new Error('请从推荐列表审核发布 FAQ');const unit=db.units.find(u=>u.id===existing.unitId)
    if(!unit||!visible(db,unit)||unit.status!=='published')throw new Error('关联知识不可访问或尚未发布')
    const faq={...existing,...item};if(!faq.question.trim()||!faq.answer.trim())throw new Error('问题和答案不能为空');faq.cache=faq.status==='published';rows.splice(rows.indexOf(existing),1,faq);write(db);return clone(faq)
   }
   if(resource==='gaps'){require(db,'gaps.manage');if(!existing)throw new Error('缺口由问答未命中记录产生');const gap={...existing,status:item.status||existing.status};if(gap.status==='resolved'&&!gap.unitId)throw new Error('请先关联知识单元');rows.splice(rows.indexOf(existing),1,gap);write(db);return clone(gap)}
   throw new Error('该资源不支持直接修改')
  },
  async remove(resource,ids){
   if(!ids.length)return
   const db=read(),me=identity(db)
   if(resource==='units'){require(db,'knowledge.delete');for(const id of ids){const u=db.units.find(u=>u.id===id);if(!u||!visible(db,u))throw new Error('部分知识不可访问，未执行删除')}db.units=db.units.filter(u=>!ids.includes(u.id));db.faqs.forEach(f=>{if(ids.includes(f.unitId)){f.cache=false;f.status='rejected'}});db.gaps.forEach(g=>{if(g.unitId&&ids.includes(g.unitId)){g.status='unresolved';delete g.unitId}})}
   else if(resource==='roles'){require(db,'org.roles.manage');if(db.users.some(u=>u.roleIds.some(id=>ids.includes(id)))||db.units.some(u=>u.acl.some(g=>g.type==='role'&&ids.includes(g.id||''))))throw new Error('角色仍被用户或知识授权使用，请先解除关联');db.roles=db.roles.filter(r=>!ids.includes(r.id));protectAdmin(db)}
   else if(resource==='departments'){require(db,'org.departments.manage');if(db.users.some(u=>ids.includes(u.departmentId))||db.departments.some(d=>ids.includes(d.parentId))||db.units.some(u=>u.acl.some(g=>g.type==='department'&&ids.includes(g.id||''))))throw new Error('部门仍有成员、下级或知识授权，不能删除');db.departments=db.departments.filter(d=>!ids.includes(d.id))}
   else if(resource==='faqs'){require(db,'faq.manage');db.faqs=db.faqs.filter(f=>!ids.includes(f.id))}
   else if(resource==='sessions'){require(db,'ai.access');db.sessions=db.sessions.filter(s=>s.userId!==me.user.id||!ids.includes(s.id))}
   else throw new Error('此资源不可删除')
   write(db)
  },
  async resetPassword(id,password){const db=read();require(db,'org.users.manage');if(password.length<8)throw new Error('密码至少 8 位');if(!db.users.some(u=>u.id===id))throw new Error('用户不存在');db.passwords[id]=password;write(db)},
  async upload(file,path,signal){const db=read();require(db,'knowledge.import');await wait(240,signal);const current=read();require(current,'knowledge.import');const job={id:uid(),name:file.name,path,size:file.size,phase:0,status:'running' as const,startedAt:now()};current.jobs.unshift(job);write(current);return clone(job)},
  async job(id){const db=read(),me=require(db,'knowledge.import'),job=db.jobs.find(j=>j.id===id);if(!job)throw new Error('任务不存在');if(job.status==='running'){job.phase=Math.min(5,Math.floor((Date.now()-Date.parse(job.startedAt))/650));if(job.phase===5){job.status='completed';const id=uid();job.unitId=id;db.units.unshift({id,code:`KB-${String(db.units.reduce((m,u)=>Math.max(m,Number(u.code.slice(3))||0),0)+1).padStart(3,'0')}`,title:job.name.replace(/\.[^.]+$/,''),content:'# 演示导入结果\n\n此内容为本地生成的占位样本，尚未调用 MinerU 或读取文件正文。请接入后端后执行真实解析。',summary:'本地演示导入，尚未真实解析',category:'未分类',tags:['演示导入'],fileType:job.name.split('.').pop()?.toUpperCase()||'TXT',attachments:[{name:job.name,size:job.size,path:job.path}],status:'draft',creatorId:me.user.id,updatedAt:now(),acl:[],versions:[]})}write(db)}return clone(job)},
  async cancelJob(id){const db=read();require(db,'knowledge.import');const job=db.jobs.find(j=>j.id===id);if(job?.status==='running'){job.status='canceled';write(db)}},
  async dashboard(period){const db=read();require(db,'dashboard.view');const cutoff=Date.now()-(period==='7d'?7:period==='30d'?30:36500)*86400000;return aggregate(db.logs.filter(l=>Date.parse(l.date)>=cutoff),db.units.map(u=>safeUnit(db,u)))},
  async reviewFaq(id,action,answer){const db=read(),me=require(db,'faq.review'),faq=db.faqs.find(f=>f.id===id);if(!faq)throw new Error('FAQ 不存在');const unit=db.units.find(u=>u.id===faq.unitId);if(!unit||!visible(db,unit)||unit.status!=='published')throw new Error('关联知识未获授权或未发布');if(action==='approve'&&!answer.trim())throw new Error('标准答案不能为空');faq.status=action==='approve'?'published':'rejected';faq.answer=answer.trim();faq.cache=action==='approve';faq.reviewerId=me.user.id;faq.reviewedAt=now();write(db)},
  async streamChat(question,sessionId,onEvent,signal){
   const db=read(),me=require(db,'ai.access');if(!question.trim()||question.length>4000)throw new Error('问题须为 1–4000 字')
   let session=db.sessions.find(s=>s.id===sessionId&&s.userId===me.user.id)
   if(sessionId&&!session)throw new Error('会话不存在或无权访问')
   if(!session){session={id:uid(),userId:me.user.id,title:question.slice(0,28),updatedAt:now(),messages:[]};db.sessions.unshift(session)}
   session.messages.push({id:uid(),role:'user',text:question,citations:[],denied:false});session.updatedAt=now()
   const terms=question.replace(/[？?，,。！!\s]/g,'');const candidates=db.units.filter(u=>u.status==='published'&&((/报销|差旅|发票|出差/.test(terms)&&u.id==='k2')||(/入职|新同事/.test(terms)&&u.id==='k1')||(/研发环境|环境接入/.test(terms)&&u.id==='k6')||[...new Set(terms.match(/[\u4e00-\u9fa5]{2}/g)||[])].some(t=>u.title.includes(t))))
   const exactFaq=db.faqs.find(f=>f.status==='published'&&f.cache&&f.question.replace(/[？?\s]/g,'')===question.replace(/[？?\s]/g,''))
   const faqUnit=exactFaq?db.units.find(u=>u.id===exactFaq.unitId&&u.status==='published'):undefined
   if(faqUnit&&!candidates.some(u=>u.id===faqUnit.id))candidates.push(faqUnit)
   const allowed=candidates.filter(u=>canRead(me.user,u)),denied=candidates.length>allowed.length
   const cached=exactFaq&&allowed.some(u=>u.id===exactFaq.unitId)?exactFaq:undefined
   const answer=cached?cached.answer:allowed.length?`根据已授权资料整理：\n\n${allowed.slice(0,2).map(u=>u.content.replace(/^# .+\n/,'' )).join('\n\n')}\n\n> 本条为本地演示回复，未调用云端模型。`:denied?'相关资料当前未获授权。请联系知识管理员申请访问权限。':'当前没有找到可支撑回答的知识，请补充问题背景或联系知识管理员完善资料。'
   const usedUnits=cached?allowed.filter(u=>u.id===cached.unitId):allowed.slice(0,2)
   const citations=usedUnits.map(u=>({unitId:u.id,code:u.code,title:u.title,location:'正文'}))
   const assistant={id:uid(),role:'assistant' as const,text:'',citations,denied,cached:!!cached,interrupted:true};session.messages.push(assistant);write(db);onEvent({type:'session',sessionId:session.id});if(denied)onEvent({type:'denied'});onEvent({type:'citations',citations});if(cached)onEvent({type:'cache',hit:true})
   const started=Date.now();let text=''
   try{for(let i=0;i<answer.length;i+=9){await wait(24,signal);const current=read(),identityNow=require(current,'ai.access');if(usedUnits.some(u=>{const latest=current.units.find(x=>x.id===u.id);return !latest||latest.status!=='published'||!canRead(identityNow.user,latest)}))throw new Error('知识访问权限已变更，请重新提问');const part=answer.slice(i,i+9);text+=part;onEvent({type:'delta',text:part})}
    const current=read(),s=current.sessions.find(s=>s.id===session!.id),m=s?.messages.find(m=>m.id===assistant.id);if(m){m.text=text;m.interrupted=false}
    current.logs.push({id:uid(),userId:me.user.id,question,unitIds:usedUnits.map(u=>u.id),tokens:cached?0:Math.ceil((question.length+answer.length)*1.4),ms:Date.now()-started,date:now()})
    if(cached){const f=current.faqs.find(f=>f.id===cached.id);if(f)f.hits++}
    if(!candidates.length){const gap=current.gaps.find(g=>g.question===question);if(gap){gap.count++;gap.lastAskedAt=now()}else current.gaps.unshift({id:uid(),question,samples:[question],count:1,lastAskedAt:now(),status:'unresolved'})}
    write(current);onEvent({type:'done',tokens:cached?0:Math.ceil((question.length+answer.length)*1.4),ms:Date.now()-started})
   }catch(error){const current=read(),m=current.sessions.find(s=>s.id===session!.id)?.messages.find(m=>m.id===assistant.id);if(m){m.text=text||'回复已中断';m.interrupted=true}write(current);throw error}
  },
  async resetDemo(){read();identity(read());storage.removeItem(storageKey);clearSession(sessionStorage)},
 }
 return service
}
