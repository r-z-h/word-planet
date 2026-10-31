import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import zhCn from 'element-plus/es/locale/lang/zh-cn'

import App from './App.vue'
import router from './router'
import './style.css'
import './styles/theme.css'
import './styles/dark-pages.css'
import { initSpeech } from './utils/speech'
import { applyMotion } from './utils/prefs'

initSpeech()
applyMotion()

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus, { locale: zhCn })
app.mount('#app')
