import {createRouter,createWebHistory} from 'vue-router'
import {useAuth} from './stores/auth'
import {getSession} from './services/session'
import type {Permission} from './types/domain'
export const destinations:{path:string;title:string;group:string;permission?:Permission;icon:string}[]=[
 {path:'/dashboard',title:'数据看板',group:'工作空间',permission:'dashboard.view',icon:'chart'},
 {path:'/knowledge/home',title:'知识工作台',group:'工作空间',permission:'knowledge.update',icon:'grid'},
 {path:'/ai/chat',title:'AI 对话',group:'工作空间',permission:'ai.access',icon:'chat'},
 {path:'/knowledge/units',title:'知识单元',group:'知识管理',permission:'knowledge.read',icon:'book'},
 {path:'/knowledge/import',title:'导入中心',group:'知识管理',permission:'knowledge.import',icon:'upload'},
 {path:'/org/users',title:'用户管理',group:'组织与权限',permission:'org.users.manage',icon:'users'},
 {path:'/org/roles',title:'角色与权限',group:'组织与权限',permission:'org.roles.manage',icon:'shield'},
 {path:'/org/departments',title:'部门管理',group:'组织与权限',permission:'org.departments.manage',icon:'tree'},
 {path:'/settlement/recommendations',title:'FAQ 推荐审核',group:'知识沉淀',permission:'faq.review',icon:'check'},
 {path:'/settlement/faqs',title:'已发布 FAQ',group:'知识沉淀',permission:'faq.manage',icon:'layers'},
 {path:'/settlement/gaps',title:'知识缺口',group:'知识沉淀',permission:'gaps.manage',icon:'target'},
]
const views={
 '/dashboard':()=>import('./views/Dashboard.vue'),'/knowledge/home':()=>import('./views/KnowledgeHome.vue'),'/ai/chat':()=>import('./views/Chat.vue'),'/knowledge/units':()=>import('./views/Knowledge.vue'),'/knowledge/import':()=>import('./views/Import.vue'),'/org/users':()=>import('./views/Users.vue'),'/org/roles':()=>import('./views/Roles.vue'),'/org/departments':()=>import('./views/Departments.vue'),'/settlement/recommendations':()=>import('./views/Faqs.vue'),'/settlement/faqs':()=>import('./views/Faqs.vue'),'/settlement/gaps':()=>import('./views/Gaps.vue'),
}
export const router=createRouter({history:createWebHistory(),scrollBehavior:()=>({top:0}),routes:[
 {path:'/login',component:()=>import('./views/Login.vue'),meta:{public:true,title:'登录'}},
 {path:'/',component:()=>import('./layouts/AppLayout.vue'),children:[
  {path:'',redirect:()=>useAuth().home},
  ...destinations.map(d=>({path:d.path,component:views[d.path as keyof typeof views],meta:{title:d.title,permission:d.permission,group:d.group}})),
  {path:'/knowledge/units/new',component:()=>import('./views/KnowledgeEditor.vue'),meta:{title:'新建知识',permission:'knowledge.create',group:'知识管理'}},
  {path:'/knowledge/units/:id/edit',component:()=>import('./views/KnowledgeEditor.vue'),meta:{title:'编辑知识',permission:'knowledge.update',group:'知识管理'}},
  {path:'/knowledge/units/:id',component:()=>import('./views/KnowledgeDetail.vue'),meta:{title:'知识详情',permission:'knowledge.read',group:'知识管理'}},
  {path:'/profile',component:()=>import('./views/Profile.vue'),meta:{title:'个人中心',group:'账户'}},
  {path:'/403',component:()=>import('./views/Status.vue'),meta:{title:'访问受限'}},
  {path:'/:pathMatch(.*)*',component:()=>import('./views/Status.vue'),meta:{title:'页面不存在'}},
 ]},
]})
router.beforeEach(async to=>{const auth=useAuth();if(!auth.ready)await auth.restore();if(!getSession()&&auth.user)auth.clear();if(!to.meta.public&&!auth.user)return {path:'/login',query:{redirect:to.fullPath}};if(to.path==='/login'&&auth.user)return auth.home;if(to.meta.permission&&!auth.has(to.meta.permission as Permission))return '/403'})
router.afterEach(to=>{document.title=`${String(to.meta.title||'工作空间')} · 知识库管理平台`})
