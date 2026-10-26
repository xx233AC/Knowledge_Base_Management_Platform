import type {User,Unit,Permission} from '../types/domain'
export function can(user:User|null,permissions:Permission[],code:Permission):boolean {return !!user&&user.status==='active'&&permissions.includes(code)}
export function canRead(user:User|null,unit:Pick<Unit,'acl'>):boolean {
 if(!user||user.status!=='active')return false
 return unit.acl.some(g=>g.type==='global'||g.type==='department'&&g.id===user.departmentId||g.type==='role'&&!!g.id&&user.roleIds.includes(g.id)||g.type==='user'&&g.id===user.id)
}
export const permissionGroups:{name:string;items:{code:Permission;label:string}[]}[]=[
 {name:'工作台',items:[{code:'dashboard.view',label:'查看系统看板'},{code:'ai.access',label:'使用 AI 问答'}]},
 {name:'组织与权限',items:[{code:'org.users.manage',label:'管理用户'},{code:'org.roles.manage',label:'管理角色与操作权限'},{code:'org.departments.manage',label:'管理部门'}]},
 {name:'知识管理',items:[{code:'knowledge.read',label:'查看获授权知识'},{code:'knowledge.create',label:'新建知识'},{code:'knowledge.update',label:'编辑知识'},{code:'knowledge.delete',label:'删除知识'},{code:'knowledge.import',label:'导入文档'},{code:'knowledge.permissions',label:'配置数据授权'}]},
 {name:'知识沉淀',items:[{code:'faq.review',label:'审核 FAQ'},{code:'faq.manage',label:'管理已发布 FAQ'},{code:'gaps.manage',label:'处理知识缺口'}]},
]
export const allPermissions=permissionGroups.flatMap(g=>g.items.map(i=>i.code))
