// 「寰宇圆满·万物生花」最高成就 · 全屏通关特效（加强版）
import { isMotionReduced } from './prefs'
import { sfxLevelUp, sfxDing, sfxShard } from './sfx'

let active = false
let styleInjected = false

function injectStyle() {
  if (styleInjected) return
  styleInjected = true
  const css = `
  .wpu{position:fixed;inset:0;z-index:9999;background:radial-gradient(circle at 50% 45%,#2a1a4d 0%,#0b0618 72%);overflow:hidden;
    font-family:"Microsoft YaHei",sans-serif;color:#fff1d6;opacity:0;transition:opacity .5s ease;cursor:pointer}
  .wpu.on{opacity:1}
  .wpu.out{opacity:0}
  .wpu.shake{animation:wpuShake .55s 1s both}
  @keyframes wpuShake{0%,100%{transform:translate(0,0)}15%{transform:translate(-9px,5px)}30%{transform:translate(8px,-6px)}
    45%{transform:translate(-6px,4px)}60%{transform:translate(5px,-3px)}80%{transform:translate(-3px,2px)}}
  .wpu-canvas{position:absolute;inset:0;width:100%;height:100%}
  .wpu-rays{position:absolute;left:50%;top:45%;width:700px;height:700px;transform:translate(-50%,-50%);border-radius:50%;
    background:repeating-conic-gradient(from 0deg,rgba(255,214,120,.30) 0deg 2.6deg,transparent 2.6deg 15deg);
    -webkit-mask:radial-gradient(circle,transparent 20%,#000 44%,transparent 74%);
    mask:radial-gradient(circle,transparent 20%,#000 44%,transparent 74%);
    opacity:0;animation:wpuFadeIn .9s ease-out 1s both, wpuSpin 10s linear 1s infinite}
  @keyframes wpuSpin{to{transform:translate(-50%,-50%) rotate(360deg)}}
  @keyframes wpuFadeIn{to{opacity:.75}}
  .wpu-flash,.wpu-flash2{position:absolute;inset:0;pointer-events:none;opacity:0}
  .wpu-flash{background:radial-gradient(circle at 50% 42%,rgba(255,255,255,.98),rgba(255,230,150,.6) 32%,transparent 66%);
    animation:wpuFlash 1.1s ease-out .95s both}
  .wpu-flash2{background:radial-gradient(circle at 50% 46%,rgba(255,240,190,.85),transparent 60%);
    animation:wpuFlash 1s ease-out 1.9s both}
  @keyframes wpuFlash{0%,100%{opacity:0}16%{opacity:.95}40%{opacity:.35}}
  .wpu-stage{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;text-align:center}
  .wpu-badge{width:200px;height:200px;filter:drop-shadow(0 0 34px rgba(255,214,120,.85));
    animation:wpuDrop 1.2s cubic-bezier(.2,.8,.2,1) .15s both, wpuFloat 3.2s ease-in-out 1.6s infinite, wpuPulse 2.4s ease-in-out 1.4s infinite}
  @keyframes wpuDrop{0%{transform:translateY(-78vh) scale(.15) rotate(-30deg);opacity:0}65%{opacity:1}100%{transform:translateY(0) scale(1) rotate(0)}}
  @keyframes wpuFloat{0%,100%{transform:translateY(0) rotate(0)}50%{transform:translateY(-11px) rotate(2deg)}}
  @keyframes wpuPulse{0%,100%{filter:drop-shadow(0 0 30px rgba(255,214,120,.8))}50%{filter:drop-shadow(0 0 56px rgba(255,214,120,1))}}
  .wpu-rings{position:absolute;width:200px;height:200px;top:calc(50% - 100px - 80px);pointer-events:none}
  .wpu-rings span{position:absolute;inset:0;border-radius:50%;border:3px solid rgba(255,214,120,.95);opacity:0;animation:wpuRing 2.6s ease-out 1.1s infinite}
  .wpu-rings span:nth-child(2){animation-delay:1.55s;border-color:rgba(255,143,177,.85)}
  .wpu-rings span:nth-child(3){animation-delay:2.0s;border-color:rgba(116,192,252,.75)}
  .wpu-rings span:nth-child(4){animation-delay:2.45s;border-color:rgba(255,243,191,.65)}
  @keyframes wpuRing{0%{transform:scale(.65);opacity:.95}100%{transform:scale(3.1);opacity:0}}
  .wpu-title{margin-top:2px}
  .wpu-title .l1,.wpu-title .l2{font-size:46px;font-weight:900;letter-spacing:.16em;color:#ffd166;opacity:0;
    text-shadow:0 0 20px rgba(255,214,120,.9),0 4px 12px rgba(0,0,0,.6);animation:wpuRise .9s cubic-bezier(.2,.9,.3,1.2) both, wpuGlow 2.4s ease-in-out 3s infinite alternate}
  .wpu-title .l1{animation-delay:2.05s,3s}
  .wpu-title .l2{animation-delay:2.5s,3s;font-size:52px}
  .wpu-title .sub{margin-top:10px;font-size:15px;letter-spacing:.62em;color:#ffe8b0;opacity:0;animation:wpuRise .8s ease-out 3.2s both}
  @keyframes wpuRise{0%{opacity:0;transform:translateY(28px) scale(.93)}100%{opacity:1;transform:translateY(0) scale(1)}}
  @keyframes wpuGlow{from{text-shadow:0 0 18px rgba(255,214,120,.8),0 4px 12px rgba(0,0,0,.6)}to{text-shadow:0 0 34px rgba(255,230,150,1),0 0 60px rgba(255,180,80,.7),0 4px 12px rgba(0,0,0,.6)}}
  .wpu-close{position:absolute;bottom:34px;left:50%;transform:translateX(-50%);font-size:12px;color:#c9b8f0;
    background:rgba(255,246,225,.1);border:1.5px solid rgba(255,232,180,.35);border-radius:99px;padding:7px 18px;
    cursor:pointer;opacity:0;animation:wpuFade .6s ease-out 4.4s both}
  @keyframes wpuFade{to{opacity:.95}}
  .wpu-close:hover{background:rgba(255,246,225,.2)}
  @media (max-width:767px){.wpu-badge{width:150px;height:150px}.wpu-title .l1{font-size:30px}.wpu-title .l2{font-size:34px}
    .wpu-rings{width:150px;height:150px;top:calc(50% - 75px - 64px)}.wpu-rays{width:520px;height:520px}}
  `
  const el = document.createElement('style')
  el.textContent = css
  document.head.appendChild(el)
}

export function playUltimate(badgeSrc = '/badges/ultimate.svg') {
  if (active) return
  active = true
  injectStyle()
  const reduced = typeof isMotionReduced === 'function' && isMotionReduced()
  const startedAt = Date.now()

  const root = document.createElement('div')
  root.className = 'wpu'
  root.innerHTML = `
    <canvas class="wpu-canvas"></canvas>
    <div class="wpu-rays"></div>
    <div class="wpu-flash"></div>
    <div class="wpu-flash2"></div>
    <div class="wpu-stage">
      <div class="wpu-rings"><span></span><span></span><span></span><span></span></div>
      <img class="wpu-badge" src="${badgeSrc}" alt="">
      <div class="wpu-title">
        <div class="l1">寰宇圆满</div>
        <div class="l2">万物生花</div>
        <div class="sub">全 宇 通 关</div>
      </div>
    </div>
    <button class="wpu-close">点击任意处关闭</button>`
  document.body.appendChild(root)
  requestAnimationFrame(() => root.classList.add('on'))
  setTimeout(() => root.classList.add('shake'), 980)
  setTimeout(() => root.classList.remove('shake'), 1560)

  try {
    sfxLevelUp()
    setTimeout(() => sfxDing(), 1950)
    setTimeout(() => sfxShard(), 3000)
  } catch {
    /* 音效失败不影响 */
  }

  let raf = 0
  let running = true

  if (!reduced) {
    const canvas = root.querySelector('.wpu-canvas')
    const ctx = canvas.getContext('2d')
    let W = 0
    let H = 0
    const dpr = Math.min(2, window.devicePixelRatio || 1)
    const resize = () => {
      W = canvas.clientWidth
      H = canvas.clientHeight
      canvas.width = Math.floor(W * dpr)
      canvas.height = Math.floor(H * dpr)
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    }
    resize()
    window.addEventListener('resize', resize)

    const colors = ['#ffd166', '#ff8fb1', '#74c0fc', '#63e6be', '#b197fc', '#fff3bf']
    const parts = []
    const rand = (a, b) => a + Math.random() * (b - a)

    // 星空穿梭
    const stars = []
    const starN = 130
    for (let i = 0; i < starN; i += 1) {
      stars.push({ a: Math.random() * Math.PI * 2, r: rand(0, Math.min(W, H) / 2), sp: rand(2, 6), tail: rand(8, 26) })
    }

    const burst = (x, y, n, spread = 6) => {
      for (let i = 0; i < n; i += 1) {
        const a = Math.random() * Math.PI * 2
        const sp = rand(1.2, spread)
        parts.push({
          x, y,
          vx: Math.cos(a) * sp,
          vy: Math.sin(a) * sp - rand(1, 4),
          life: rand(55, 125),
          age: 0,
          g: 0.06,
          color: colors[(Math.random() * colors.length) | 0],
          size: rand(1.6, 4),
          kind: Math.random() < 0.35 ? 'rect' : 'dot',
          rot: rand(0, Math.PI),
          vr: rand(-0.22, 0.22)
        })
      }
    }
    const petal = () => parts.push({
      x: rand(0, W), y: H + rand(0, 60), vx: rand(-0.5, 0.5), vy: rand(-1.6, -0.8),
      life: rand(220, 360), age: 0, g: -0.004, sway: rand(0.4, 1.2), phase: rand(0, 6.28),
      color: Math.random() < 0.6 ? '#ff9db4' : '#ffd166', size: rand(4, 8),
      kind: 'petal', rot: rand(0, 6.28), vr: rand(-0.05, 0.05)
    })
    const confetti = () => parts.push({
      x: rand(0, W), y: -12, vx: rand(-0.7, 0.7), vy: rand(1.4, 3.6), g: 0.055,
      life: rand(150, 260), age: 0, color: colors[(Math.random() * colors.length) | 0],
      size: rand(3, 6), kind: 'rect', rot: rand(0, Math.PI), vr: rand(-0.2, 0.2)
    })

    let last = performance.now()
    let lastBurst = 0
    let lastConfetti = 0
    let lastPetal = 0
    const frame = (t) => {
      if (!running) return
      const dt = Math.min(34, t - last) / 16
      last = t
      ctx.clearRect(0, 0, W, H)

      // 星空穿梭（前 2.6s）
      if (t < 2600) {
        const fade = t < 1800 ? 1 : Math.max(0, 1 - (t - 1800) / 800)
        ctx.lineCap = 'round'
        for (const s of stars) {
          s.r += s.sp * dt
          if (s.r > Math.hypot(W, H) / 1.4) { s.r = rand(0, 30); s.a = Math.random() * Math.PI * 2 }
          const cx = W / 2
          const cy = H * 0.44
          const x1 = cx + Math.cos(s.a) * s.r
          const y1 = cy + Math.sin(s.a) * s.r
          const x2 = cx + Math.cos(s.a) * (s.r + s.tail * (s.r / 300 + 0.4))
          const y2 = cy + Math.sin(s.a) * (s.r + s.tail * (s.r / 300 + 0.4))
          ctx.globalAlpha = 0.55 * fade
          ctx.strokeStyle = '#fff3bf'
          ctx.lineWidth = 1.6
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke()
        }
        ctx.globalAlpha = 1
      }

      if (t > 950) {
        if (t - lastBurst > 300) {
          burst(rand(W * 0.1, W * 0.9), rand(H * 0.08, H * 0.58), 100, 8)
          lastBurst = t
        }
        if (t - lastConfetti > 55) { confetti(); confetti(); lastConfetti = t }
        if (t - lastPetal > 140) { petal(); if (Math.random() < 0.6) petal(); lastPetal = t }
      }

      const cx = W / 2
      for (let i = parts.length - 1; i >= 0; i -= 1) {
        const p = parts[i]
        p.age += 1
        if (p.kind === 'petal') {
          p.phase += 0.05
          p.x += p.vx * dt + Math.sin(p.phase) * p.sway * dt
          p.y += p.vy * dt
        } else {
          p.x += p.vx * dt
          p.y += p.vy * dt
          p.vy += p.g * dt
        }
        p.rot += p.vr
        const a = Math.max(0, 1 - p.age / p.life)
        if (a <= 0 || p.y < -40 || p.y > H + 30) { parts.splice(i, 1); continue }
        ctx.globalAlpha = a
        ctx.fillStyle = p.color
        if (p.kind === 'petal') {
          ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot)
          ctx.beginPath(); ctx.ellipse(0, 0, p.size, p.size / 2.2, 0, 0, Math.PI * 2); ctx.fill(); ctx.restore()
        } else if (p.kind === 'rect') {
          ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot)
          ctx.fillRect(-p.size / 2, -p.size / 4, p.size, p.size / 2); ctx.restore()
        } else {
          ctx.beginPath(); ctx.arc(p.x, p.y, p.size / 2, 0, Math.PI * 2); ctx.fill()
        }
      }
      ctx.globalAlpha = 1
      raf = requestAnimationFrame(frame)
    }
    raf = requestAnimationFrame(frame)
    root._wpuCleanup = () => { running = false; cancelAnimationFrame(raf); window.removeEventListener('resize', resize) }
  }

  const close = () => {
    if (Date.now() - startedAt < 1000) return
    if (root._wpuCleanup) root._wpuCleanup()
    root.classList.add('out')
    setTimeout(() => { root.remove(); active = false }, 380)
    document.removeEventListener('keydown', onKey)
  }
  const onKey = (e) => { if (e.key === 'Escape') close() }
  root.addEventListener('click', close)
  document.addEventListener('keydown', onKey)
}
