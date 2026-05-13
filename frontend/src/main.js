import { createApp } from 'vue'
import { ElLoadingDirective } from 'element-plus'
import 'element-plus/es/components/message-box/style/css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import './style.css'
import App from './App.vue'
import router from './router/index.js'
import { initializeTheme } from './lib/theme.js'

initializeTheme()
createApp(App)
  .use(router)
  .directive('loading', ElLoadingDirective)
  .mount('#app')
