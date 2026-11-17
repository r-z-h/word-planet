// 最高成就解锁：先播放 100s 旅程 CG，结束后中央点亮星球徽记
import { sfxLevelUp, sfxDing, sfxShard } from './sfx'

let active = false
let styleInjected = false

function injectStyle() {
  if (styleInjected) return
  styleInjected = true
  const css = `
  /* ===== 全屏旅程视频 ===== */
  .wpuv{position:fixed;inset:0;z-index:9998;background:#000;display:flex;align-items:center;justify-content:center}
  .wpuv video{width:100%;height:100%;object-fit:contain;background:#000}
  .wpuv-skip{position:absolute;top:14px;right:16px;z-index:2;padding:7px 14px;border-radius:99px;border:1.5px solid rgba(255,255,255,.35);
    background:rgba(0,0,0,.45);color:#fff1d6;font-family:"Microsoft YaHei",sans-serif;font-size:12px;cursor:pointer}
  .wpuv-skip:hover{background:rgba(0,0,0,.7)}
  .wpuv-play{position:absolute;z-index:3;display:none;width:84px;height:84px;border-radius:50%;border:3px solid #ffd166;
    background:rgba(30,18,55,.85);color:#ffd166;font-size:30px;cursor:pointer;place-items:center}
  /* ===== 徽章点亮 ===== */
  .wpuv-reveal{position:fixed;inset:0;z-index:9999;background:radial-gradient(circle at 50% 48%,#241543 0%,#0b0618 70%);
    display:flex;align-items:center;justify-content:center;overflow:hidden;opacity:0;transition:opacity .35s ease;cursor:pointer}
  .wpuv-reveal.on{opacity:1}
  .wpuv-reveal.out{opacity:0}
  .wpuv-rays{position:absolute;width:620px;height:620px;border-radius:50%;
    background:repeating-conic-gradient(from 0deg,rgba(255,214,120,.28) 0deg 2.6deg,transparent 2.6deg 15deg);
    -webkit-mask:radial-gradient(circle,transparent 18%,#000 44%,transparent 76%);
    mask:radial-gradient(circle,transparent 18%,#000 44%,transparent 76%);
    animation:wpuvSpin 9s linear infinite, wpuvFadeIn .8s ease-out both}
  @keyframes wpuvSpin{to{transform:rotate(360deg)}}
  @keyframes wpuvFadeIn{from{opacity:0}to{opacity:.7}}
  .wpuv-glow{position:absolute;width:420px;height:420px;border-radius:50%;
    background:radial-gradient(circle,rgba(255,214,120,.55),rgba(255,214,120,0) 68%);animation:wpuvPulse 2.2s ease-in-out infinite}
  @keyframes wpuvPulse{0%,100%{transform:scale(.9);opacity:.6}50%{transform:scale(1.15);opacity:1}}
  .wpuv-badge{position:relative;width:230px;height:230px;filter:drop-shadow(0 0 30px rgba(255,214,120,.9));
    animation:wpuvBadge 1.5s cubic-bezier(.2,.9,.25,1.15) both}
  @keyframes wpuvBadge{
    0%{opacity:0;transform:scale(.35) rotate(-12deg);filter:brightness(.25) drop-shadow(0 0 0 rgba(255,214,120,0))}
    55%{opacity:1;transform:scale(1.12) rotate(3deg);filter:brightness(1.7) drop-shadow(0 0 50px rgba(255,214,120,1))}
    100%{opacity:1;transform:scale(1) rotate(0);filter:brightness(1) drop-shadow(0 0 30px rgba(255,214,120,.9))}
  }
  .wpuv-rings{position:absolute;width:230px;height:230px;pointer-events:none}
  .wpuv-rings span{position:absolute;inset:0;border-radius:50%;border:3px solid rgba(255,214,120,.9);opacity:0;animation:wpuvRing 2.4s ease-out .5s infinite}
  .wpuv-rings span:nth-child(2){animation-delay:1.0s;border-color:rgba(255,143,177,.8)}
  .wpuv-rings span:nth-child(3){animation-delay:1.5s;border-color:rgba(116,192,252,.7)}
  @keyframes wpuvRing{0%{transform:scale(.7);opacity:.9}100%{transform:scale(2.7);opacity:0}}
  .wpuv-flash{position:absolute;inset:0;background:radial-gradient(circle,rgba(255,255,255,.95),rgba(255,230,150,.5) 34%,transparent 66%);
    opacity:0;pointer-events:none;animation:wpuvFlash 1s ease-out .95s both}
  @keyframes wpuvFlash{0%,100%{opacity:0}18%{opacity:.9}45%{opacity:.25}}
  .wpuv-label{margin-top:18px;font-family:"Microsoft YaHei",sans-serif;font-size:18px;font-weight:900;color:#ffd166;
    text-shadow:0 0 16px rgba(255,214,120,.9);opacity:0;animation:wpuvLabel .7s ease-out 1.5s both}
  @keyframes wpuvLabel{to{opacity:1}}
  .wpuv-col{display:flex;flex-direction:column;align-items:center;position:relative}
  .wpuv-close{position:absolute;bottom:30px;left:50%;transform:translateX(-50%);font-family:"Microsoft YaHei",sans-serif;
    font-size:12px;color:#c9b8f0;border:1.5px solid rgba(255,232,180,.35);border-radius:99px;padding:7px 16px;
    background:rgba(255,246,225,.1);opacity:0;animation:wpuvLabel .6s ease-out 3.4s both}
  @media (max-width:767px){.wpuv-badge{width:170px;height:170px}.wpuv-rays{width:460px;height:460px}.wpuv-glow{width:300px;height:300px}}
  `
  const el = document.createElement('style')
  el.textContent = css
  document.head.appendChild(el)
}

export function playBadgeReveal(badgeSrc = '/badges/ultimate.svg') {
  injectStyle()
  const frag = document.createElement('div')
  frag.className = 'wpuv-reveal'
  frag.innerHTML = `
    <div class="wpuv-rays"></div>
    <div class="wpuv-glow"></div>
    <div class="wpuv-col">
      <div class="wpuv-rings"><span></span><span></span><span></span></div>
      <img class="wpuv-badge" src="${badgeSrc}" alt="">
      <div class="wpuv-label">寰宇圆满 · 万物生花</div>
    </div>
    <div class="wpuv-flash"></div>
    <div class="wpuv-close">点击任意处关闭</div>`
  document.body.appendChild(frag)
  requestAnimationFrame(() => frag.classList.add('on'))
  try { sfxLevelUp(); setTimeout(() => sfxShard(), 900) } catch { /* ignore */ }
  const opened = Date.now()
  const close = () => {
    if (Date.now() - opened < 900) return
    frag.classList.add('out')
    setTimeout(() => frag.remove(), 350)
    document.removeEventListener('keydown', onKey)
    active = false
  }
  const onKey = (e) => { if (e.key === 'Escape') close() }
  frag.addEventListener('click', close)
  document.addEventListener('keydown', onKey)
  setTimeout(() => { if (document.body.contains(frag)) close() }, 5200)
}

export function playUltimateSequence(videoSrc = '/videos/ultimate_journey.mp4', badgeSrc = '/badges/ultimate.svg') {
  if (active) return
  active = true
  injectStyle()
  const wrap = document.createElement('div')
  wrap.className = 'wpuv'
  wrap.innerHTML = `
    <video src="${videoSrc}" playsinline preload="auto"></video>
    <button class="wpuv-skip">跳过 ›</button>
    <button class="wpuv-play">▶</button>`
  document.body.appendChild(wrap)
  const video = wrap.querySelector('video')
  const skip = wrap.querySelector('.wpuv-skip')
  const playBtn = wrap.querySelector('.wpuv-play')
  let done = false
  const finish = () => {
    if (done) return
    done = true
    wrap.remove()
    playBadgeReveal(badgeSrc)
  }
  video.addEventListener('ended', finish)
  video.addEventListener('error', finish)
  skip.addEventListener('click', (e) => { e.stopPropagation(); finish() })
  playBtn.addEventListener('click', (e) => { e.stopPropagation(); video.play().catch(() => {}); playBtn.style.display = 'none' })
  const p = video.play()
  if (p && p.catch) p.catch(() => { playBtn.style.display = 'grid' })
}
