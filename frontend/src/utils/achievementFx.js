// 成就解锁动效（简约版）：右下角滑入"成就解锁卡" + 徽章弹跳 + 金光 + 星光
import { playUltimate } from './ultimateFx'
const META = {
  complete_l1_first: { name: '初学有成', icon: '🎓' },
  streak_3: { name: '连续三天', icon: '🔥' },
  streak_7: { name: '连续七天', icon: '/badges/streak7.svg' },
  answer_100: { name: '百题达成', icon: '💯' },
  complete_level: { name: '学有所成', icon: '🏫' },
  perfect_set: { name: '完美一套', icon: '/badges/perfect_set.svg' },
  level_test_pass: { name: '能力初试', icon: '🎖️' },
  ultimate_all: { name: '寰宇圆满·万物生花', icon: '/badges/ultimate.svg' }
}

const queue = []
let showing = false
let styleInjected = false

function injectStyle() {
  if (styleInjected) return
  styleInjected = true
  const css = `
  .wp-af{position:fixed;right:24px;bottom:24px;z-index:4000;display:flex;gap:12px;align-items:center;width:320px;
    background:linear-gradient(180deg,#2a1a4d,#1e1237);border:2px solid rgba(255,214,120,.6);border-radius:16px;
    padding:12px 14px;box-shadow:0 16px 40px rgba(0,0,0,.55);opacity:0;transform:translateY(24px) scale(.96);
    transition:transform .45s cubic-bezier(.2,.9,.25,1.2),opacity .35s ease;font-family:"Microsoft YaHei",sans-serif}
  .wp-af.show{opacity:1;transform:translateY(0) scale(1)}
  .wp-af .aw{position:relative;width:56px;height:56px;flex:none;display:grid;place-items:center}
  .wp-af .aw img{width:46px;height:46px;object-fit:contain;animation:wpPop .6s cubic-bezier(.2,1.4,.3,1.4)}
  .wp-af .aw .emo{font-size:38px;line-height:1;animation:wpPop .6s cubic-bezier(.2,1.4,.3,1.4)}
  @keyframes wpPop{0%{transform:scale(.4) rotate(-12deg)}60%{transform:scale(1.18) rotate(6deg)}100%{transform:scale(1) rotate(0)}}
  .wp-af .ring{position:absolute;width:56px;height:56px;border-radius:50%;border:2px solid rgba(255,214,120,.9);animation:wpRing .7s ease-out forwards}
  @keyframes wpRing{0%{transform:scale(.6);opacity:.9}100%{transform:scale(2.1);opacity:0}}
  .wp-af .lab{font-size:9.5px;letter-spacing:.14em;color:#ffd166;font-weight:900}
  .wp-af .nm{font-size:15px;font-weight:900;color:#fff1d6;margin-top:2px}
  .wp-af .cd{font-size:10.5px;color:#c9b8f0;margin-top:2px}
  .wp-af .sp{position:absolute;width:4px;height:4px;border-radius:50%;background:#ffe066;left:22px;top:22px}
  `
  const el = document.createElement('style')
  el.textContent = css
  document.head.appendChild(el)
}

function renderIcon(icon) {
  if (/^(\/|https?:|data:)/.test(icon)) {
    return `<img src="${icon}" alt="" />`
  }
  return `<span class="emo">${icon}</span>`
}

function pump() {
  if (showing || !queue.length) return
  injectStyle()
  showing = true
  const item = queue.shift()
  const card = document.createElement('div')
  card.className = 'wp-af'
  card.innerHTML = `
    <div class="aw"><span class="ring"></span>${renderIcon(item.icon)}</div>
    <div class="txt"><div class="lab">成就解锁</div><div class="nm">${item.name}</div><div class="cd">${item.desc || ''}</div></div>`
  document.body.appendChild(card)
  const aw = card.querySelector('.aw')
  for (let i = 0; i < 6; i += 1) {
    const s = document.createElement('span')
    s.className = 'sp'
    const a = (Math.PI * 2 * i) / 6
    const r = 26 + Math.random() * 10
    s.style.transform = `translate(${Math.cos(a) * r}px, ${Math.sin(a) * r}px)`
    s.style.opacity = '1'
    aw.appendChild(s)
  }
  requestAnimationFrame(() => card.classList.add('show'))
  setTimeout(() => {
    card.classList.remove('show')
    setTimeout(() => {
      card.remove()
      showing = false
      pump()
    }, 400)
  }, 1600)
}

export function showAchievementUnlock(code, desc = '') {
  const meta = META[code]
  if (!meta) return
  if (code === 'ultimate_all') {
    playUltimate(meta.icon || '/badges/ultimate.svg')
    return
  }
  queue.push({ ...meta, desc })
  pump()
}
