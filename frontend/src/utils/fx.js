/** 轻量视觉特效工具 */
export function shakeSoft(sel = '.v2-shell') {
  const el = document.querySelector(sel)
  if (!el) return
  el.classList.remove('fx-shake')
  void el.offsetWidth
  el.classList.add('fx-shake')
  setTimeout(() => el.classList.remove('fx-shake'), 460)
}

/** 生成一组粒子（返回可直接绑定的 style 对象数组） */
export function burst(count = 14, opts = {}) {
  const colors = opts.colors || ['#ffcd4c', '#ffd166', '#6ff0c4', '#9fb6ff', '#ff9db4']
  return Array.from({ length: count }, (_, i) => {
    const ang = (Math.PI * 2 * i) / count + Math.random() * 0.4
    const dist = (opts.dist || 78) * (0.55 + Math.random() * 0.7)
    return {
      id: `${Date.now()}-${i}-${Math.random().toString(16).slice(2, 6)}`,
      style: {
        '--tx': (Math.cos(ang) * dist).toFixed(1) + 'px',
        '--ty': (Math.sin(ang) * dist).toFixed(1) + 'px',
        background: colors[i % colors.length],
        animationDelay: (i % 6) * 18 + 'ms',
        width: (5 + Math.random() * 5).toFixed(1) + 'px',
        height: (5 + Math.random() * 5).toFixed(1) + 'px'
      }
    }
  })
}
