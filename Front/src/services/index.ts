import {createDemo} from './demo'
import {api} from './api'
export const dataMode=import.meta.env.VITE_DATA_MODE==='api'?'api':'demo'
export const service=dataMode==='api'?api:createDemo(localStorage,sessionStorage)
