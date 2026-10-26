import type {ChatEvent} from '../types/domain'
export async function consumeSSE(stream:ReadableStream<Uint8Array>,onEvent:(event:ChatEvent)=>void,signal?:AbortSignal) {
 const reader=stream.getReader(),decoder=new TextDecoder();let buffer='',finished=false
 function consume(final=false){
  buffer=buffer.replace(/\r\n/g,'\n')
  let split:number
  while((split=buffer.indexOf('\n\n'))>=0){
   const block=buffer.slice(0,split);buffer=buffer.slice(split+2)
   let type='message';const lines:string[]=[]
   for(const line of block.split('\n')){if(line.startsWith('event:'))type=line.slice(6).trim();if(line.startsWith('data:'))lines.push(line.slice(5).replace(/^ /,''))}
   if(!lines.length)continue
   const raw=lines.join('\n');if(raw==='[DONE]'){finished=true;onEvent({type:'done'});return}
   let data:any;try{data=JSON.parse(raw)}catch{throw new Error('AI 服务返回了无效的数据格式')}
   const eventType=data.type||type
   if(eventType==='error')throw new Error(data.message||'AI 服务暂不可用')
   if(!['session','delta','citations','denied','cache','done'].includes(eventType))continue
   if(eventType==='done')finished=true
   onEvent({...data,type:eventType} as ChatEvent)
   if(finished)return
  }
  if(final&&buffer.trim()&&!buffer.trim().startsWith(':'))throw new Error('AI 响应在事件完成前中断')
 }
 const abort=()=>{void reader.cancel().catch(()=>{})}
 signal?.addEventListener('abort',abort,{once:true})
 try{while(true){if(signal?.aborted)throw new DOMException('已停止','AbortError');const {done,value}=await reader.read();if(signal?.aborted)throw new DOMException('已停止','AbortError');if(done)break;buffer+=decoder.decode(value,{stream:true});consume();if(finished)break}
 if(!finished){buffer+=decoder.decode();consume(true)}if(!finished)throw new Error('AI 响应意外中断，请重试')
 }finally{signal?.removeEventListener('abort',abort);await reader.cancel().catch(()=>{});reader.releaseLock()}
}
