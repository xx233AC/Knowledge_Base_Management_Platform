import {defineStore} from 'pinia'
import {ref,computed} from 'vue'
import {service} from '../services'
import {getSession,setSession,clearSession} from '../services/session'
import {can} from '../domain/permissions'
import type {User,Role,Permission} from '../types/domain'
export const useAuth=defineStore('auth',()=>{
 const user=ref<User|null>(null),roles=ref<Role[]>([]),permissions=ref<Permission[]>([]),ready=ref(false)
 const has=(code:Permission)=>can(user.value,permissions.value,code)
 const home=computed(()=>has('dashboard.view')?'/dashboard':has('knowledge.update')?'/knowledge/home':has('ai.access')?'/ai/chat':has('knowledge.read')?'/knowledge/units':'/profile')
 function clear(){user.value=null;roles.value=[];permissions.value=[];clearSession();ready.value=true}
 async function refresh(){if(!getSession()){clear();return}const me=await service.me();user.value=me.user;roles.value=me.roles;permissions.value=me.permissions;ready.value=true}
 async function restore(){try{await refresh()}catch{clear()}}
 async function login(username:string,password:string){const result=await service.login(username,password);setSession(result);user.value=result.user;roles.value=result.roles;permissions.value=result.permissions;ready.value=true}
 async function logout(){try{await service.logout()}finally{clear()}}
 return {user,roles,permissions,ready,home,has,refresh,restore,login,logout,clear}
})
