<script setup lang="ts">
import {computed,ref,watch} from 'vue'
import {useRoute,useRouter} from 'vue-router'
import {useAuth} from '../stores/auth'
import {destinations} from '../router'
import {dataMode} from '../services'
import Brand from '../components/Brand.vue'
import Icon from '../components/Icon.vue'
const auth=useAuth(),route=useRoute(),router=useRouter(),open=ref(false)
const groups=computed(()=>[...new Set(destinations.map(d=>d.group))].map(name=>({name,items:destinations.filter(d=>d.group===name&&(!d.permission||auth.has(d.permission)))})).filter(g=>g.items.length))
watch(()=>route.fullPath,()=>{open.value=false})
async function logout(){try{await auth.logout()}finally{router.replace('/login')}}
</script>
<template><div class="app-shell"><button v-if="open" class="nav-backdrop" aria-label="关闭导航" @click="open=false" /><aside class="sidebar" :class="{open}"><Brand /><div class="workspace-label"><span class="live-dot" />内部团队空间<span>01</span></div><nav aria-label="主导航"><div v-for="group in groups" :key="group.name" class="nav-group"><p>{{group.name}}</p><RouterLink v-for="item in group.items" :key="item.path" :to="item.path" class="nav-item"><Icon :name="item.icon" /><span>{{item.title}}</span></RouterLink></div></nav><div class="sidebar-bottom"><RouterLink to="/profile" class="account-link"><span class="avatar">{{auth.user?.displayName.slice(0,1)}}</span><span><strong>{{auth.user?.displayName}}</strong><small>{{auth.roles.map(r=>r.name).join(' / ')}}</small></span><Icon name="arrow" :size="15" /></RouterLink><button class="logout" @click="logout"><Icon name="logout" :size="16" />退出登录</button></div></aside><div class="app-main"><header class="topbar"><div class="breadcrumb"><button class="icon-button menu-toggle" @click="open=!open" :aria-expanded="open" aria-label="切换导航"><Icon name="menu" /></button><span>{{route.meta.group||'工作空间'}}</span><span class="slash">/</span><strong>{{route.meta.title}}</strong></div><div class="topbar-right"><span class="mode-badge" :class="dataMode"><i />{{dataMode==='demo'?'本地演示':'后端连接'}}</span><RouterLink to="/profile" class="topbar-user">{{auth.user?.displayName}}<Icon name="user" :size="16" /></RouterLink></div></header><div v-if="dataMode==='demo'" class="mode-note">演示空间 · 仅使用虚构数据，变更保存在当前浏览器；解析与 AI 回复均为模拟。</div><main class="workspace"><RouterView :key="route.path" /></main><footer class="app-footer"><span>团队知识 · 有据可答</span><span>知识库管理平台</span></footer></div></div></template>
