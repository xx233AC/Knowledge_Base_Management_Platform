import type {AccessLog,Unit} from '../types/domain'
export function aggregate(logs:AccessLog[],units:Unit[]) {
 const visits=logs.length,uv=new Set(logs.map(l=>l.userId)).size,tokens=logs.reduce((s,l)=>s+l.tokens,0),avgMs=visits?logs.reduce((s,l)=>s+l.ms,0)/visits:0
 const days=[...new Set(logs.map(l=>l.date.slice(0,10)))].sort()
 const trend=days.map(date=>({date,visits:logs.filter(l=>l.date.startsWith(date)).length,tokens:logs.filter(l=>l.date.startsWith(date)).reduce((s,l)=>s+l.tokens,0)}))
 const questionCounts=new Map<string,number>(),unitCounts=new Map<string,number>()
 logs.forEach(l=>{questionCounts.set(l.question,(questionCounts.get(l.question)||0)+1);l.unitIds.forEach(id=>unitCounts.set(id,(unitCounts.get(id)||0)+1))})
 const questions=[...questionCounts].sort((a,b)=>b[1]-a[1]).slice(0,5)
 const hotUnits=[...unitCounts].sort((a,b)=>b[1]-a[1]).slice(0,5).map(([id,count])=>({id,title:units.find(u=>u.id===id)?.title||'未授权或已删除知识',count}))
 const bins=[{label:'< 1 秒',min:0,max:1000},{label:'1–2 秒',min:1000,max:2000},{label:'2–3 秒',min:2000,max:3000},{label:'≥ 3 秒',min:3000,max:Infinity}].map(b=>({...b,count:logs.filter(l=>l.ms>=b.min&&l.ms<b.max).length}))
 return {visits,uv,tokens,avgMs,unitCount:units.length,trend,questions,hotUnits,bins}
}
export type DashboardStats=ReturnType<typeof aggregate>
