import {createApp} from 'vue'
import {createPinia} from 'pinia'
import {ElDialog,ElSelect,ElOption,ElTreeSelect,ElTree,ElSwitch,ElPagination,ElCheckbox,ElCheckboxGroup,ElInput,ElTag} from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import '@fontsource/inter/latin-400.css'
import '@fontsource/inter/latin-500.css'
import '@fontsource/inter/latin-600.css'
import './styles/main.css'
import App from './App.vue'
import {router} from './router'
const app=createApp(App)
app.use(createPinia())
for(const c of [ElDialog,ElSelect,ElOption,ElTreeSelect,ElTree,ElSwitch,ElPagination,ElCheckbox,ElCheckboxGroup,ElInput,ElTag])app.use(c)
app.use(router).mount('#app')
