<script setup lang="ts">
import {ref,onMounted,onBeforeUnmount} from 'vue'
const canvas=ref<HTMLCanvasElement>(),wrap=ref<HTMLDivElement>()
let frame=0,observer:ResizeObserver,intersection:IntersectionObserver,context:CanvasRenderingContext2D|null,w=0,h=0,visible=true,until=0
let points:{x:number;y:number;ox:number;oy:number}[]=[],pointer={x:-999,y:-999}
const media=matchMedia('(prefers-reduced-motion: reduce)')
function paint(time:number){frame=0;if(!context||!visible||document.hidden)return;context.clearRect(0,0,w,h);let moving=false;for(const p of points){const dx=p.x-pointer.x,dy=p.y-pointer.y,d=Math.hypot(dx,dy),influence=media.matches?0:Math.max(0,1-d/130),tx=dx/Math.max(1,d)*influence*10,ty=dy/Math.max(1,d)*influence*10;p.ox+=(tx-p.ox)*.12;p.oy+=(ty-p.oy)*.12;moving ||=Math.abs(p.ox-tx)+Math.abs(p.oy-ty)>.08;context.fillStyle=influence>.1?'rgba(131,200,171,.4)':'rgba(130,170,150,.18)';context.fillRect(p.x+p.ox,p.y+p.oy,3,3)}if(!media.matches&&(moving||time<until))frame=requestAnimationFrame(paint)}
function wake(){until=performance.now()+500;if(!frame&&visible&&!document.hidden)frame=requestAnimationFrame(paint)}
function resize(){if(!canvas.value||!wrap.value)return;const r=wrap.value.getBoundingClientRect(),dpr=Math.min(devicePixelRatio,2);w=r.width;h=r.height;canvas.value.width=w*dpr;canvas.value.height=h*dpr;context=canvas.value.getContext('2d');context?.setTransform(dpr,0,0,dpr,0,0);points=[];for(let y=18;y<h;y+=27)for(let x=18;x<w;x+=27)points.push({x,y,ox:0,oy:0});wake()}
function move(e:PointerEvent){const r=wrap.value!.getBoundingClientRect();pointer={x:e.clientX-r.left,y:e.clientY-r.top};wake()}
function leave(){pointer={x:-999,y:-999};wake()}
function visibility(){if(document.hidden){cancelAnimationFrame(frame);frame=0}else wake()}
onMounted(()=>{const parent=wrap.value!.parentElement!;parent.addEventListener('pointermove',move);parent.addEventListener('pointerleave',leave);observer=new ResizeObserver(resize);observer.observe(wrap.value!);intersection=new IntersectionObserver(([e])=>{visible=!!e?.isIntersecting;if(visible)wake();else{cancelAnimationFrame(frame);frame=0}});intersection.observe(wrap.value!);document.addEventListener('visibilitychange',visibility);media.addEventListener('change',wake);resize()})
onBeforeUnmount(()=>{cancelAnimationFrame(frame);observer?.disconnect();intersection?.disconnect();wrap.value?.parentElement?.removeEventListener('pointermove',move);wrap.value?.parentElement?.removeEventListener('pointerleave',leave);document.removeEventListener('visibilitychange',visibility);media.removeEventListener('change',wake)})
</script>
<template><div ref="wrap" class="dot-field" aria-hidden="true"><canvas ref="canvas" /></div></template>
