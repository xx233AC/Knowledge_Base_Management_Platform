import type {EntityMap,Resource,Permission} from '../types/domain'
export type Database={ [K in Resource]:EntityMap[K][] } & {passwords:Record<string,string>;schema:number}
export function createSeed():Database {
 const knowledgePermissions:Permission[]=['knowledge.read','knowledge.create','knowledge.update','knowledge.delete','knowledge.import','knowledge.permissions','ai.access','faq.review','faq.manage','gaps.manage']
 const roles:EntityMap['roles'][]=[
  {id:'r_sys',name:'系统管理员',code:'system_admin',description:'组织管理与系统运行监控',permissions:['dashboard.view','org.users.manage','org.roles.manage','org.departments.manage','knowledge.read','ai.access']},
  {id:'r_kb',name:'知识管理员',code:'knowledge_admin',description:'知识维护、数据授权与知识沉淀',permissions:knowledgePermissions},
  {id:'r_member',name:'普通用户',code:'member',description:'AI 问答与获授权知识访问',permissions:['ai.access','knowledge.read']},
 ]
 const names=['林序','周宁','陈一','许知','苏禾','程越','沈青','陆川'],usernames=['admin','knowledge','member','xuzhi','suhe','chengyue','shenqing','luchuan']
 const users:EntityMap['users'][]=names.map((displayName,i)=>({id:`u${i+1}`,displayName,username:usernames[i]!,departmentId:['d1','d2','d2','d3','d4','d2','d3','d4'][i]!,roleIds:[i===0?'r_sys':i===1?'r_kb':'r_member'],status:'active',createdAt:'2026-10-01T09:00:00+08:00'}))
 const departments=[{id:'d1',name:'团队管理',parentId:'',leaderId:'u1',sort:0},{id:'d2',name:'产品研发部',parentId:'d1',leaderId:'u2',sort:1},{id:'d3',name:'财务部',parentId:'d1',leaderId:'u4',sort:2},{id:'d4',name:'客户服务部',parentId:'d1',leaderId:'u5',sort:3}]
 const titles=['新员工入职手册','差旅报销操作指南','产品需求协作规范','员工休假管理办法','项目立项与审批规范','研发环境接入说明','团队知识维护约定','远程办公协作约定','客户服务沟通规范','项目复盘记录模板','知识发布检查清单','会议纪要归档约定']
 const contents=[
  '# 新员工入职手册\n\n欢迎加入团队。\n\n## 入职第一天\n\n1. 向人事提交身份及入职材料。\n2. 领取办公设备，激活团队账号。\n3. 阅读信息安全规范，与直属负责人确认工作安排。',
  '# 差旅报销操作指南\n\n## 报销材料\n\n出差前请先提交出差申请，审批通过后再预订行程。\n\n报销需提交：\n\n- 已审批的出差申请\n- 费用发票与对应支付凭证\n- 按实际支出填写的费用明细\n\n请在行程结束后 **10 个工作日内** 提交。特殊事项请联系财务负责人。',
  '# 产品需求协作规范\n\n需求从问题出发，描述使用场景、验收条件和优先级。\n\n## 评审\n\n产品、研发及测试共同评审，确认边界后进入排期。',
  '# 员工休假管理办法\n\n请通过团队审批系统提交请假申请，填写起止日期及交接人。年假余额可在个人档案中查询。',
  '# 项目立项与审批规范\n\n提交项目目标、责任人、预算与里程碑，经负责人审核后正式启动。',
  '# 研发环境接入说明\n\n向研发负责人申请测试环境账号，开启双因素认证。禁止将生产密钥写入代码或文档。',
  '# 团队知识维护约定\n\n每份文档归属一个知识单元。更新时保留变更说明，并核对数据授权。',
  '# 远程办公协作约定\n\n提前登记办公安排，保持团队日历和任务状态同步。',
  '# 客户服务沟通规范\n\n记录客户问题、处理过程与反馈结果。客户隐私信息应先脱敏后归档。',
  '# 项目复盘记录模板\n\n## 目标与结果\n\n## 经验与问题\n\n## 后续行动\n\n每项行动标注责任人与截止时间。',
  '# 知识发布检查清单\n\n核对内容、引用、版本和授权范围，再发布。',
  '# 会议纪要归档约定\n\n纪要包含主题、参与人、决策与行动项。会后由记录人归档。',
 ]
 const units:EntityMap['units'][]=titles.map((title,i)=>({id:`k${i+1}`,code:`KB-${String(i+1).padStart(3,'0')}`,title,content:contents[i]!,summary:contents[i]!.replace(/[#*\n]/g,' ').slice(0,80),category:['人事制度','财务制度','产品研发','人事制度','项目管理','产品研发','团队协作','团队协作','客户服务','项目管理','团队协作','团队协作'][i]!,tags:[i%2?'操作指南':'团队规范'],fileType:['PDF','PDF','Markdown','Word'][i%4]!,attachments:[{name:title+['.pdf','.pdf','.md','.docx'][i%4],size:24000+i*1024}],status:i<9?'published':'draft',creatorId:'u2',updatedAt:`2026-10-${String(12+i%8).padStart(2,'0')}T10:30:00+08:00`,acl:i===7||i===10?[]:i===4?[{type:'role',id:'r_kb'},{type:'user',id:'u1'}]:i===5?[{type:'department',id:'d2'},{type:'role',id:'r_kb'}]:[{type:'global'}],versions:[{version:1,date:'2026-10-12T10:30:00+08:00',editor:'周宁',content:contents[i]!,title}]}))
 const questions=['差旅报销需要哪些材料？','新同事入职要做什么？','需求如何发起评审？','请假如何申请？','研发环境如何接入？','客户问题如何归档？']
 const dayCounts=[4,6,5,8,6,7,6];let index=0
 const logs:EntityMap['logs'][]=dayCounts.flatMap((count,day)=>Array.from({length:count},()=>{const n=index++;return{id:`l${n}`,userId:`u${n%6+1}`,question:questions[n%6]!,unitIds:[`k${[2,1,3,4,6,9][n%6]}`],tokens:500+n%7*40,ms:1200+n%7*400,date:`2026-10-${15+day}T10:${String(n%60).padStart(2,'0')}:00+08:00`}}))
 const faqs:EntityMap['faqs'][]=[{id:'f1',question:questions[0]!,answer:'请提交已审批的出差申请、费用发票、对应支付凭证和费用明细，并在行程结束后 10 个工作日内提交报销。',unitId:'k2',frequency:7,status:'pending_review',cache:false,category:'财务制度',hits:0},{id:'f2',question:questions[1]!,answer:'请提交入职材料，领取设备、激活团队账号，并与直属负责人确认工作安排。',unitId:'k1',frequency:7,status:'published',cache:true,category:'人事制度',hits:3,reviewerId:'u2',reviewedAt:'2026-10-20T09:00:00+08:00'}]
 const gaps:EntityMap['gaps'][]=[{id:'g1',question:'外部培训费用如何申请？',samples:['外部培训费用如何申请？','参加技术会议可以报销吗？'],count:5,lastAskedAt:'2026-10-21T11:30:00+08:00',status:'unresolved'},{id:'g2',question:'客户服务交接如何确认？',samples:['客户服务交接如何确认？'],count:3,lastAskedAt:'2026-10-21T10:00:00+08:00',status:'unresolved'}]
 return {schema:1,users,roles,departments,units,logs,faqs,gaps,jobs:[],sessions:[],passwords:Object.fromEntries(users.map(u=>[u.id,'Demo@123']))}
}
