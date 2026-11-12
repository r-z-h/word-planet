// 让「返回」固定按钮贴着"页面内容框"右边缘外侧（随框宽变化自动调整）
function update() {
  const card =
    document.querySelector('.page > .card') ||
    document.querySelector('.wp-dark.page > .card')
  if (!card) return
  const rect = card.getBoundingClientRect()
  const gap = 18
  const btnW = window.innerWidth <= 767 ? 40 : 46
  let right = window.innerWidth - rect.right - gap - btnW
  if (right < 8) right = 8
  document.documentElement.style.setProperty('--back-right', `${Math.round(right)}px`)
}

let raf = 0
function schedule() {
  if (raf) cancelAnimationFrame(raf)
  raf = requestAnimationFrame(update)
}

export function initBackPositioning(router) {
  if (router && router.afterEach) {
    router.afterEach(() => {
      setTimeout(schedule, 30)
      setTimeout(schedule, 350)
    })
  }
  window.addEventListener('resize', schedule)
  window.addEventListener('load', schedule)
  setTimeout(schedule, 300)
}
