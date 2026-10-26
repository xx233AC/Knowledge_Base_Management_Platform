<script setup lang="ts">
import {ref,nextTick} from 'vue'
import {useResource,useTask,confirmAction} from '../composables/useData'
import {permissionGroups,allPermissions} from '../domain/permissions'
import {service} from '../services'
import {useAuth} from '../stores/auth'
import type {Role,Permission} from '../types/domain'
import PageHeader from '../components/PageHeader.vue'
import LoadState from '../components/LoadState.vue'
import Icon from '../components/Icon.vue'
const roles=useResource('roles'),auth=useAuth(),task=useTask(),dialog=ref(false),tree=ref<any>(),draft=ref<Partial<Role>>({})
const treeData=permissionGroups.map(g=>({id:g.name,label:g.name,children:g.items.map(i=>({id:i.code,label:i.label}))}))
async function edit(role?:Role){draft.value=role?structuredClone(role):{name:'',code:'',description:'',permissions:[]};dialog.value=true;await nextTick();tree.value?.setCheckedKeys(draft.value.permissions||[])}
async function save(){draft.value.permissions=tree.value.getCheckedKeys().filter((key:string)=>allPermissions.includes(key as Permission));await task.run(async()=>{await service.save('roles',draft.value);dialog.value=false;await roles.load();await auth.refresh()})}
async function remove(role:Role){if(!await confirmAction(`删除角色「${role.name}」？已关联用户或知识授权的角色不能删除。`))return;await task.run(async()=>{await service.remove('roles',[role.id]);await roles.load()},'角色已删除')}
</script>
<template><PageHeader title="角色与操作权限" description="控制角色可访问的菜单和可执行的操作；知识内容访问由数据授权单独决定。"><button class="btn primary" @click="edit()"><Icon name="plus"/>新增角色</button></PageHeader><LoadState :loading="roles.loading.value" :error="roles.error.value" :empty="!roles.items.value.length" @retry="roles.load"><div class="table-wrap"><table class="data-table"><thead><tr><th>角色名称 / 编码</th><th>职责说明</th><th>操作权限数</th><th>操作</th></tr></thead><tbody><tr v-for="role in roles.items.value" :key="role.id"><td><strong class="identity">{{role.name}}</strong><span class="sub">{{role.code}}</span></td><td>{{role.description||'—'}}</td><td class="num">{{role.permissions.length}}</td><td><div class="row-actions"><button class="text-button" @click="edit(role)">配置权限</button><button class="text-button danger" @click="remove(role)">删除</button></div></td></tr></tbody></table></div></LoadState><el-dialog v-model="dialog" :title="draft.id?'编辑角色与权限':'新增角色'" width="580px" :close-on-click-modal="false"><form id="role-form" @submit.prevent="save"><div class="form-grid"><label class="field">角色名称<input v-model="draft.name" required maxlength="40"></label><label class="field">角色编码<input v-model="draft.code" required pattern="[A-Za-z][A-Za-z0-9_]{2,39}" title="3–40 位字母、数字或下划线，以字母开头"></label><label class="field span-2">职责说明<input v-model="draft.description" maxlength="200"></label></div><div class="field">菜单与操作权限<div class="permissions-box"><el-tree ref="tree" :data="treeData" node-key="id" show-checkbox default-expand-all aria-label="菜单与操作权限树" /></div></div><p v-if="task.error.value" class="field-error">{{task.error.value}}</p></form><template #footer><button class="btn quiet" @click="dialog=false">取消</button><button class="btn primary" form="role-form" :disabled="task.busy.value">保存权限</button></template></el-dialog></template>
