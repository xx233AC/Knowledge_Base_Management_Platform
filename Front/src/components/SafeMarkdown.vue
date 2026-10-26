<script setup lang="ts">
import {computed} from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
const props=defineProps<{content:string}>(),md=new MarkdownIt({html:false,linkify:true,breaks:true})
const html=computed(()=>{
  const clean=DOMPurify.sanitize(md.render(props.content),{FORBID_TAGS:['style','iframe','form','input'],FORBID_ATTR:['style','target']})
  const doc=new DOMParser().parseFromString(clean,'text/html')
  // Only signed in-app assets may render: blocks external tracking pixels and arbitrary URLs.
  doc.querySelectorAll('img').forEach(img=>{
    const src=img.getAttribute('src')||''
    if(!src.startsWith('/api/knowledge/assets/')){img.remove();return}
    img.setAttribute('loading','lazy')
    if(!img.getAttribute('alt'))img.setAttribute('alt','文档图片')
  })
  return doc.body.innerHTML
})
</script>
<template><div class="markdown" v-html="html" /></template>
