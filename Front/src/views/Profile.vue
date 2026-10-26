<script setup lang="ts">
import {ref,onMounted} from 'vue'
import {useRouter} from 'vue-router'
import {useAuth} from '../stores/auth'
import {service,dataMode} from '../services'
import {permissionGroups} from '../domain/permissions'
import {confirmAction,useTask,formatDate} from '../composables/useData'
import PageHeader from '../components/PageHeader.vue'
const auth=useAuth(),router=useRouter(),task=useTask(),department=ref('')
onMounted(async()=>{try{const me=await service.me();department.value=me.department?.name||me.user.departmentId}catch{}})
async function reset(){if(!await confirmAction('将清除当前浏览器中的演示变更、会话和导入任务，恢复初始样本。','重置演示空间'))return;await task.run(async()=>{await service.resetDemo();auth.clear();await router.replace('/login')},'演示数据已重置')}
</script>
<template><PageHeader title="个人中心" description="你的团队身份与当前访问权限。" /><div class="two-columns"><section class="panel"><h2>账户信息</h2><dl class="detail-list"><dt>姓名</dt><dd>{{auth.user?.displayName}}</dd><dt>用户名</dt><dd>{{auth.user?.username}}</dd><dt>所属部门</dt><dd>{{department}}</dd><dt>拥有角色</dt><dd>{{auth.roles.map(r=>r.name).join('、')}}</dd><dt>账号状态</dt><dd><span class="status success">启用</span></dd><dt>创建时间</dt><dd>{{formatDate(auth.user?.createdAt||'')}}</dd></dl></section><section class="panel"><h2>操作权限</h2><div v-for="group in permissionGroups" :key="group.name" class="permission-summary"><h3>{{group.name}}</h3><div class="tag-row"><span v-for="item in group.items.filter(i=>auth.has(i.code))" :key="item.code" class="status">{{item.label}}</span><span v-if="!group.items.some(i=>auth.has(i.code))" class="muted small">未分配操作权限</span></div></div></section></div><section v-if="dataMode==='demo'" class="panel settings-panel"><div><h2>演示空间</h2><p class="muted">所有样本仅保存在当前浏览器。重置后恢复初始账号和数据。</p></div><button class="btn danger" :disabled="task.busy.value" @click="reset">重置演示数据</button></section></template>
