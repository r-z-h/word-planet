import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import basicSsl from '@vitejs/plugin-basic-ssl'

/**
 * 两种启动模式：
 *   默认（HTTP，端口 5173）—— 电脑用。http://localhost 属于安全上下文，
 *                              麦克风 / Service Worker 在这台机器上照样可用。
 *   WP_HTTPS=1（HTTPS，端口 5174）—— 手机用。局域网 IP 走 http 不是安全上下文，
 *                              必须 https，浏览器会提示自签证书，选择继续访问。
 */
const useHttps = process.env.WP_HTTPS === '1'
const port = Number(process.env.WP_PORT || (useHttps ? 5174 : 5173))

export default defineConfig({
  plugins: useHttps ? [vue(), basicSsl()] : [vue()],
  // 电脑(5173)和手机(5174)两个 dev 实例会同时运行；若共用 node_modules/.vite 会互相
  // 抢占依赖预构建，导致 deps 反复停留在 deps_temp_* 而报 504 Outdated Optimize Dep（整页空白）。
  // 故按模式各用独立缓存目录。
  cacheDir: useHttps ? 'node_modules/.vite-mobile' : 'node_modules/.vite-desktop',
  server: {
    host: '0.0.0.0',
    port,
    strictPort: true,
    https: useHttps,
    // 公网穿透（Cloudflare Tunnel 等）临时演示：域名不在白名单时 Vite 5.4.21
    // 会直接返回 "Blocked request"。仅开发服务器需要；正式部署走 nginx 静态文件，不经过这里。
    allowedHosts: true,
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
