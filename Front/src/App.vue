<script setup lang="ts">
import {onMounted,onBeforeUnmount} from 'vue'
import {useRouter} from 'vue-router'
import {useAuth} from './stores/auth'
const auth=useAuth(),router=useRouter()
function unauthorized(){auth.clear();router.replace('/login')}
async function revalidate(){if(!auth.user)return;try{await auth.refresh();const p=router.currentRoute.value.meta.permission;if(p&&!auth.has(p as any))router.replace('/403')}catch{unauthorized()}}
onMounted(()=>{window.addEventListener('kb:unauthorized',unauthorized);window.addEventListener('focus',revalidate)})
onBeforeUnmount(()=>{window.removeEventListener('kb:unauthorized',unauthorized);window.removeEventListener('focus',revalidate)})
</script>
<template><RouterView /></template>
