import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import basicSsl from '@vitejs/plugin-basic-ssl'

// 手机访问 + 语音识别需要安全上下文，所以默认启用 HTTPS（自签证书）
export default defineConfig({
  plugins: [vue(), basicSsl()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    https: true,
    // 编辑器/Agent 写文件时会生成 .xxx.tmpdir 临时目录，watcher 碰到会 EBUSY 崩溃
    watch: {
      ignored: ['**/*.tmpdir/**', '**/.??*.tmpdir/**']
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true
      }
    }
  }
})
