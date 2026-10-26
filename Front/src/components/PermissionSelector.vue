<script setup lang="ts">
import {computed} from 'vue'
import {useResource} from '../composables/useData'
import type {Grant} from '../types/domain'
const props=defineProps<{modelValue:Grant[]}>(),emit=defineEmits<{ 'update:modelValue':[value:Grant[]] }>()
const users=useResource('users'),roles=useResource('roles'),departments=useResource('departments')
const global=computed({get:()=>props.modelValue.some(g=>g.type==='global'),set:v=>emit('update:modelValue',[...props.modelValue.filter(g=>g.type!=='global'),...(v?[{type:'global' as const}]:[])])})
function selected(type:Grant['type']){return props.modelValue.filter(g=>g.type===type).map(g=>g.id!)}
function change(type:Grant['type'],ids:string[]){emit('update:modelValue',[...props.modelValue.filter(g=>g.type!==type),...ids.map(id=>({type,id}))])}
const groups=computed(()=>[{type:'department' as const,label:'部门',rows:departments.items.value.map(d=>({id:d.id,name:d.name})),error:departments.error.value},{type:'role' as const,label:'角色',rows:roles.items.value.map(r=>({id:r.id,name:r.name})),error:roles.error.value},{type:'user' as const,label:'个人',rows:users.items.value.filter(u=>u.status==='active').map(u=>({id:u.id,name:u.displayName})),error:users.error.value}])
</script>
<template><div class="permission-selector"><label class="check-label"><input type="checkbox" v-model="global">全局可访问（系统内已登录用户）</label><fieldset v-for="group in groups" :key="group.type" class="permission-group"><legend>{{group.label}}</legend><el-select :model-value="selected(group.type)" @update:model-value="change(group.type,$event)" multiple filterable collapse-tags collapse-tags-tooltip :placeholder="`选择${group.label}`" :aria-label="`授权${group.label}`"><el-option v-for="row in group.rows" :key="row.id" :label="row.name" :value="row.id" /></el-select><p v-if="group.error" class="field-error">{{group.error}}</p></fieldset><p class="notice" :class="{warning:!modelValue.length}">{{modelValue.length?'任一授权条件匹配即可访问；下级部门不自动继承。':'尚未设置授权，所有用户默认不可访问此知识。'}}</p></div></template>
