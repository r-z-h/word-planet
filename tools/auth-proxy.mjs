// Word Planet 公网演示用的「口令门」反向代理（零依赖，仅用 Node 内置模块）。
//
// 作用：监听 127.0.0.1:8080，先让访客通过自带登录页验证口令，再把请求（含
// WebSocket/HMR）原样转发给本机 Vite dev server 127.0.0.1:5173。cloudflared 指向 8080。
//
// 为什么不用浏览器原生 HTTP Basic 弹框（重要）：
//   手机 / 微信内置浏览器对 401 + WWW-Authenticate 的处理有缺陷：输错口令后会把错误凭据
//   记进系统，之后再打开只加载到缓存的 index.html（有标题）却取不到 /src/main.js（401），
//   页面一直空白且重开也不恢复。改为「自带登录表单 + 签名 Cookie」后，输错只在本页提示，
//   不触发任何系统级凭据缓存，且不再与前端自身的 `Authorization: Bearer` 抢头。
//
// 认证流程：
//   1) 未登录 → 返回本站登录页（HTTP 401，但不带 WWW-Authenticate，浏览器不会弹框）；
//   2) 提交表单 POST /__gate/login → 口令正确则下发 HMAC 签名 Cookie（wp_gate）并 302 回原页；
//   3) 之后所有请求凭 Cookie 放行；口令错误只在本页显示「账号或密码错误」。
//   4) 兼容：仍接受 `Authorization: Basic`（供脚本/curl 自动化），但不会主动下发 WWW-Authenticate。
//
// 环境变量：
//   WP_PROXY_USER      用户名（默认 family）
//   WP_PROXY_PASS      密码（必填，为空拒绝启动）
//   WP_PROXY_PORT      监听端口（默认 8080）
//   WP_PROXY_UPSTREAM  上游端口（默认 5173）

import http from 'node:http'
import net from 'node:net'
import crypto from 'node:crypto'

const USER = process.env.WP_PROXY_USER || 'family'
const PASS = process.env.WP_PROXY_PASS || ''
const PORT = Number(process.env.WP_PROXY_PORT || 8080)
const UP_HOST = '127.0.0.1'
const UP_PORT = Number(process.env.WP_PROXY_UPSTREAM || 5173)

const COOKIE_NAME = 'wp_gate'
const COOKIE_MAX_AGE = 7 * 24 * 3600 // 7 天
const LOGIN_PATH = '/__gate/login'
// 由口令派生的签名 Cookie 值：不知道口令就无法伪造
const GATE_TOKEN = crypto.createHmac('sha256', PASS || 'unset').update('wp-gate-v1').digest('hex')

if (!PASS) {
  console.error('[auth-proxy] WP_PROXY_PASS 为空，拒绝启动（未设置口令就等于裸奔）')
  process.exit(1)
}

function safeEqual(a, b) {
  const ba = Buffer.from(a)
  const bb = Buffer.from(b)
  if (ba.length !== bb.length) return false
  return crypto.timingSafeEqual(ba, bb)
}

function parseCookies(header) {
  const out = {}
  const s = header || ''
  s.split(';').forEach((part) => {
    const i = part.indexOf('=')
    if (i > 0) {
      const k = part.slice(0, i).trim()
      const v = part.slice(i + 1).trim()
      if (k) out[k] = v
    }
  })
  return out
}

function basicOk(req) {
  const header = req.headers['authorization'] || ''
  const m = /^Basic\s+(.+)$/i.exec(header)
  if (!m) return false
  let decoded
  try {
    decoded = Buffer.from(m[1], 'base64').toString('utf8')
  } catch {
    return false
  }
  const i = decoded.indexOf(':')
  if (i < 0) return false
  const u = decoded.slice(0, i)
  const p = decoded.slice(i + 1)
  return safeEqual(u, USER) && safeEqual(p, PASS)
}

function cookieOk(req) {
  const c = parseCookies(req.headers['cookie'])
  const v = c[COOKIE_NAME]
  if (!v) return false
  return safeEqual(v, GATE_TOKEN)
}

// 返回 'basic' | 'cookie' | false
function authMode(req) {
  if (basicOk(req)) return 'basic'
  if (cookieOk(req)) return 'cookie'
  return false
}

function isHttps(req) {
  const p = (req.headers['x-forwarded-proto'] || '').split(',')[0].trim()
  return p === 'https' || !!req.socket.encrypted
}

function gateSetCookie(req) {
  const base = `${COOKIE_NAME}=${GATE_TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=${COOKIE_MAX_AGE}`
  return isHttps(req) ? base + '; Secure' : base
}

function stripGateCookie(cookieHeader) {
  if (!cookieHeader) return cookieHeader
  return cookieHeader
    .split(';')
    .filter((p) => p.split('=')[0].trim() !== COOKIE_NAME)
    .join('; ')
}

function wantsHtml(req) {
  return String(req.headers['accept'] || '').includes('text/html')
}

function nextSafe(next) {
  return typeof next === 'string' && next.startsWith('/') && !next.startsWith('//') ? next : '/'
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  })[c])
}

function loginPage(next, error) {
  const n = nextSafe(next)
  const errHtml = error ? `<div class="err">${escapeHtml(error)}</div>` : ''
  return `<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<title>Word Planet · 英语闯关</title>
<style>
  *{box-sizing:border-box}
  body{margin:0;min-height:100vh;display:flex;align-items:center;justify-content:center;
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue","PingFang SC","Microsoft YaHei",sans-serif;
       background:linear-gradient(160deg,#eef4ff,#e6fbf3);color:#1f2937;padding:16px}
  .card{width:100%;max-width:360px;background:#fff;border-radius:16px;
        box-shadow:0 10px 30px rgba(31,41,55,.12);padding:28px 22px}
  .logo{text-align:center;font-size:22px;font-weight:800;letter-spacing:.5px;color:#2563eb;margin-bottom:4px}
  .sub{text-align:center;font-size:13px;color:#6b7280;margin-bottom:14px}
  label{display:block;font-size:13px;color:#374151;margin:12px 0 6px}
  input{width:100%;height:44px;padding:0 12px;font-size:16px;border:1px solid #d1d5db;border-radius:10px;outline:none}
  input:focus{border-color:#2563eb;box-shadow:0 0 0 3px rgba(37,99,235,.15)}
  button{width:100%;height:46px;margin-top:20px;border:0;border-radius:10px;background:#2563eb;color:#fff;font-size:16px;font-weight:600}
  button:active{background:#1d4ed8}
  .err{margin-top:6px;padding:10px 12px;border-radius:10px;background:#fef2f2;color:#b91c1c;font-size:13px;text-align:center}
  .tip{margin-top:16px;font-size:12px;color:#9ca3af;text-align:center}
</style>
</head>
<body>
  <form class="card" method="POST" action="${LOGIN_PATH}" autocomplete="on">
    <div class="logo">Word Planet</div>
    <div class="sub">请输入演示口令后继续</div>
    ${errHtml}
    <label for="u">账号</label>
    <input id="u" name="u" type="text" autocomplete="username" autocapitalize="none" autocorrect="off" spellcheck="false" required />
    <label for="p">密码</label>
    <input id="p" name="p" type="password" autocomplete="current-password" required />
    <input type="hidden" name="next" value="${escapeHtml(n)}" />
    <button type="submit">进入</button>
    <div class="tip">仅用于临时演示，请勿外传</div>
  </form>
</body>
</html>`
}

function sendLoginPage(res, next, error) {
  res.writeHead(401, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(loginPage(next, error))
}

const server = http.createServer((req, res) => {
  const url = req.url || '/'
  const path = url.split('?')[0]

  // 登录表单提交
  if (path === LOGIN_PATH && req.method === 'POST') {
    let body = ''
    req.on('data', (c) => {
      body += c
      if (body.length > 20000) req.destroy()
    })
    req.on('end', () => {
      let u = ''
      let p = ''
      let next = '/'
      try {
        const params = new URLSearchParams(body)
        u = params.get('u') || ''
        p = params.get('p') || ''
        next = params.get('next') || '/'
      } catch (e) {
        /* ignore */
      }
      if (safeEqual(u, USER) && safeEqual(p, PASS)) {
        const target = nextSafe(next)
        res.writeHead(302, {
          'Set-Cookie': gateSetCookie(req),
          Location: target,
          'Cache-Control': 'no-store'
        })
        res.end()
      } else {
        sendLoginPage(res, next, '账号或密码错误，请重试')
      }
    })
    return
  }

  // 直接打开登录页（GET）
  if (path === LOGIN_PATH && req.method === 'GET') {
    const q = new URLSearchParams(url.split('?')[1] || '')
    sendLoginPage(res, q.get('next') || '/', '')
    return
  }

  const mode = authMode(req)
  if (!mode) {
    if (wantsHtml(req)) {
      sendLoginPage(res, url, '')
    } else {
      // 静态资源 / 接口请求：返回 401 纯文本，且不带 WWW-Authenticate（不触发浏览器弹框）
      res.writeHead(401, { 'Content-Type': 'text/plain; charset=utf-8', 'Cache-Control': 'no-store' })
      res.end('需要先通过演示口令验证')
    }
    return
  }

  // 已认证，转发到上游
  const headers = { ...req.headers }
  // 应用只用 Bearer；把任何 Basic 头（口令门凭据或手机残留的错误凭据）都剥掉，避免干扰后端
  if (headers['authorization'] && /^Basic\s/i.test(headers['authorization'])) delete headers['authorization']
  if (headers['cookie'] !== undefined) headers['cookie'] = stripGateCookie(headers['cookie'])

  const upstream = http.request(
    { host: UP_HOST, port: UP_PORT, method: req.method, path: req.url, headers },
    (up) => {
      const respHeaders = { ...up.headers }
      if (mode === 'basic') {
        // 走 Basic 认证的（脚本/curl）也顺手种下 Cookie
        const prev = up.headers['set-cookie']
        const list = prev ? (Array.isArray(prev) ? prev.slice() : [prev]) : []
        list.push(gateSetCookie(req))
        respHeaders['set-cookie'] = list
      }
      res.writeHead(up.statusCode || 502, respHeaders)
      up.pipe(res)
    }
  )
  upstream.on('error', (err) => {
    if (!res.headersSent) {
      res.writeHead(502, { 'Content-Type': 'text/plain; charset=utf-8' })
    }
    res.end('上游服务未就绪：' + err.message)
  })
  req.pipe(upstream)
})

// WebSocket / Vite HMR：把 Upgrade 请求当作原始 TCP 透传
server.on('upgrade', (req, socket, head) => {
  const mode = authMode(req)
  if (!mode) {
    socket.write('HTTP/1.1 401 Unauthorized\r\nConnection: close\r\n\r\n')
    socket.destroy()
    return
  }

  const upstream = net.connect(UP_PORT, UP_HOST, () => {
    let raw = `${req.method} ${req.url} HTTP/1.1\r\n`
    for (const [k, v] of Object.entries(req.headers)) {
      if (/^authorization$/i.test(k) && /^Basic\s/i.test(v)) continue
      if (Array.isArray(v)) v.forEach((x) => (raw += `${k}: ${x}\r\n`))
      else raw += `${k}: ${v}\r\n`
    }
    raw += '\r\n'
    upstream.write(raw)
    if (head && head.length) upstream.write(head)
    socket.pipe(upstream)
    upstream.pipe(socket)
  })
  upstream.on('error', () => socket.destroy())
  socket.on('error', () => upstream.destroy())
})

server.listen(PORT, '127.0.0.1', () => {
  console.log(
    `[auth-proxy] listening on http://127.0.0.1:${PORT} -> ${UP_HOST}:${UP_PORT} (user=${USER})`
  )
})

server.on('error', (err) => {
  console.error('[auth-proxy] ' + err.message)
  process.exit(1)
})
