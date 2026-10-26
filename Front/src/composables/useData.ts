import {ref,shallowRef,onMounted,onBeforeUnmount} from 'vue'
import {ElMessage,ElMessageBox} from 'element-plus'
import {service} from '../services'
import type {EntityMap,Resource} from '../types/domain'
export function useResource<K extends Resource>(resource:K,immediate=true){
 const items=shallowRef<EntityMap[K][]>([]),loading=ref(false),error=ref('')
 let revision=0
 async function load(){const ticket=++revision;loading.value=true;error.value='';try{const result=await service.list(resource);if(ticket===revision)items.value=result}catch(e){if(ticket===revision){items.value=[];error.value=errorText(e)}}finally{if(ticket===revision)loading.value=false}}
 if(immediate){onMounted(()=>{void load();window.addEventListener('focus',load)});onBeforeUnmount(()=>window.removeEventListener('focus',load))}
 return {items,loading,error,load}
}
export function errorText(error:unknown){return error instanceof Error?error.message:'操作失败，请重试'}
export function useTask(){const busy=ref(false),error=ref('');async function run<T>(fn:()=>Promise<T>,message='保存成功'):Promise<T|undefined>{if(busy.value)return;busy.value=true;error.value='';try{const result=await fn();if(message)ElMessage.success(message);return result}catch(e){error.value=errorText(e);ElMessage.error(error.value)}finally{busy.value=false}}return {busy,error,run}}
export async function confirmAction(message:string,title='确认操作'){try{await ElMessageBox.confirm(message,title,{confirmButtonText:'确认',cancelButtonText:'取消',type:'warning',closeOnClickModal:false});return true}catch{return false}}
export const formatDate=(value:string)=>value?new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).format(new Date(value)):'—'
export const formatSize=(value:number)=>value<1024?`${value} B`:value<1024*1024?`${(value/1024).toFixed(1)} KB`:`${(value/1024/1024).toFixed(1)} MB`
