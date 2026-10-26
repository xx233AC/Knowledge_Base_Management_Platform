<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount,watch} from 'vue'
import {use,init,type EChartsType,type EChartsCoreOption} from 'echarts/core'
import {LineChart,BarChart} from 'echarts/charts'
import {GridComponent,TooltipComponent} from 'echarts/components'
import {CanvasRenderer} from 'echarts/renderers'
use([LineChart,BarChart,GridComponent,TooltipComponent,CanvasRenderer])
const props=withDefaults(defineProps<{labels:string[];values:number[];type?:'line'|'bar';unit?:string;label:string;height?:number}>(),{type:'line',unit:'',height:180})
const root=ref<HTMLDivElement>();let chart:EChartsType|undefined,observer:ResizeObserver
function render(){if(!chart)return;const options:EChartsCoreOption={animation:!matchMedia('(prefers-reduced-motion: reduce)').matches,animationDuration:450,color:['#83c8ab'],textStyle:{fontFamily:'Inter,Microsoft YaHei,sans-serif'},grid:{top:18,right:18,bottom:32,left:44},tooltip:{trigger:'axis',backgroundColor:'#202723',borderColor:'#35403b',textStyle:{color:'#e6ede9'},valueFormatter:(v:unknown)=>`${v} ${props.unit}`},xAxis:{type:'category',data:props.labels,boundaryGap:props.type==='bar',axisLine:{show:false},axisTick:{show:false},axisLabel:{color:'#9eafa5',fontSize:11,hideOverlap:true}},yAxis:{type:'value',min:0,minInterval:1,axisLabel:{color:'#9eafa5',fontSize:11},splitNumber:3,splitLine:{lineStyle:{color:'#35403b'}},axisLine:{show:false}},series:[{type:props.type,data:props.values,smooth:false,showSymbol:false,lineStyle:{width:2},barMaxWidth:28,itemStyle:{borderRadius:0}}]};chart.setOption(options,true)}
onMounted(()=>{chart=init(root.value!,undefined,{renderer:'canvas'});render();observer=new ResizeObserver(()=>chart?.resize());observer.observe(root.value!)})
watch(()=>[props.labels,props.values,props.type],render,{deep:true})
onBeforeUnmount(()=>{observer?.disconnect();chart?.dispose()})
</script>
<template><div ref="root" class="chart" role="img" :aria-label="`${label}：${labels.map((l,i)=>l+' '+values[i]+unit).join('；')}`" :style="{height:height+'px'}" /></template>
