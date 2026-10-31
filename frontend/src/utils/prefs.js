/** 本机偏好：音量 / 减弱动效 / 缓存清理 */

export function isMotionReduced() {
  return localStorage.getItem('wp_reduce_motion') === '1'
}

export function applyMotion() {
  document.documentElement.classList.toggle('reduce-motion', isMotionReduced())
}

export function setMotionReduced(v) {
  localStorage.setItem('wp_reduce_motion', v ? '1' : '0')
  applyMotion()
}

export function getVolume() {
  const raw = localStorage.getItem('wp_volume')
  if (raw === null) return 0.8
  const n = Number(raw)
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n / 100)) : 0.8
}

export function setVolume(percent) {
  localStorage.setItem('wp_volume', String(Math.round(Math.min(100, Math.max(0, percent)))))
}

/** 清本机缓存但保留登录 token */
export function clearLocalCache() {
  const token = localStorage.getItem('wp_token')
  const sound = localStorage.getItem('wp_sound')
  const volume = localStorage.getItem('wp_volume')
  const motion = localStorage.getItem('wp_reduce_motion')
  localStorage.clear()
  if (token) localStorage.setItem('wp_token', token)
  if (sound) localStorage.setItem('wp_sound', sound)
  if (volume) localStorage.setItem('wp_volume', volume)
  if (motion) localStorage.setItem('wp_reduce_motion', motion)
}
