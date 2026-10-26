export const maxFiles=Number(import.meta.env.VITE_UPLOAD_MAX_FILES)||30
export const maxBytes=(Number(import.meta.env.VITE_UPLOAD_MAX_MB)||50)*1024*1024
export const concurrency=Math.max(1,Math.min(6,Number(import.meta.env.VITE_UPLOAD_CONCURRENCY)||3))
export function validateFile(file:Pick<File,'name'|'size'>){
 if(!/\.(pdf|md|markdown|docx?|txt)$/i.test(file.name))return '仅支持 PDF、Markdown、Word 和 TXT'
 if(file.size===0)return '文件为空，请重新选择'
 if(file.size>maxBytes)return `文件超过 ${maxBytes/1024/1024} MB 上限`
 return ''
}
