<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
import {useRoute} from 'vue-router'
import {service,dataMode} from '../services'
import {useAuth} from '../stores/auth'
import {formatDate,formatSize,errorText} from '../composables/useData'
import type {Unit,Version} from '../types/domain'
import PageHeader from '../components/PageHeader.vue'
import LoadState from '../components/LoadState.vue'
import SafeMarkdown from '../components/SafeMarkdown.vue'
import Icon from '../components/Icon.vue'
const route=useRoute(),auth=useAuth(),unit=ref<Unit>(),loading=ref(true),error=ref(''),version=ref<Version>(),versionOpen=ref(false)
let revision=0
async function load(){const ticket=++revision;loading.value=true;error.value='';unit.value=undefined;versionOpen.value=false;version.value=undefined;try{const result=await service.getUnit(String(route.params.id));if(ticket===revision)unit.value=result}catch(e){if(ticket===revision)error.value=errorText(e)}finally{if(ticket===revision)loading.value=false}}
onMounted(()=>{void load();window.addEventListener('focus',load)})
onBeforeUnmount(()=>window.removeEventListener('focus',load))
function showVersion(v:Version){version.value=v;versionOpen.value=true}
</script>
<template><PageHeader title="知识详情" :description="unit?.code||'访问已授权的知识内容。'"><RouterLink to="/knowledge/units" class="btn quiet">返回列表</RouterLink><RouterLink v-if="unit&&auth.has('knowledge.update')" :to="`/knowledge/units/${unit.id}/edit`" class="btn primary">编辑知识</RouterLink></PageHeader><LoadState :loading="loading" :error="error" @retry="load"><div v-if="unit" class="editor-layout"><article class="panel"><header class="detail-heading"><h2 style="font-size:24px">{{unit.title}}</h2><div class="tag-row"><span class="status" :class="unit.status==='published'?'success':''">{{unit.status==='published'?'已发布':'草稿'}}</span><span class="status">{{unit.category}}</span><span v-for="tag in unit.tags" :key="tag" class="status">{{tag}}</span></div><p class="small faint">{{unit.code}} · {{unit.fileType}} · 更新于 {{formatDate(unit.updatedAt)}}</p></header><SafeMarkdown :content="unit.content" /></article><aside class="stack"><section class="panel"><h2>访问范围</h2><p class="small muted" style="margin-top:14px">{{unit.acl.some(g=>g.type==='global')?'系统内已登录用户可访问':`已配置 ${unit.acl.length} 项混合授权，满足任意一项即可访问。`}}</p></section><section class="panel"><h2>源附件</h2><div v-for="file in unit.attachments" :key="file.name" class="attachment-row"><Icon name="file"/><div class="break">{{file.name}}<p class="small faint">{{formatSize(file.size)}}</p></div></div><p v-if="!unit.attachments.length" class="small faint" style="margin-top:14px">无附件 · 手动编写</p><p v-if="dataMode==='demo'&&unit.attachments.length" class="small faint" style="margin-top:14px">演示文件信息，不含原始附件。</p></section><section class="panel"><h2>版本记录</h2><div v-for="v in [...unit.versions].reverse()" :key="v.version" class="version-row"><strong>版本 {{v.version}}</strong><p>{{v.editor}} · {{formatDate(v.date)}}</p><button class="text-button" @click="showVersion(v)">查看内容</button></div><p v-if="!unit.versions.length" class="small faint" style="margin-top:14px">尚无编辑记录</p></section></aside></div></LoadState><el-dialog v-model="versionOpen" :title="`版本 ${version?.version||''} · ${version?.title||''}`" width="760px"><SafeMarkdown :content="version?.content||''" /></el-dialog></template>
