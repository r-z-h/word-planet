/**
 * 统一的语音合成封装。
 *
 * 解决 Edge / Chrome 上「第一次点朗读要等三四秒」的问题：
 *  - 浏览器加载声音列表是异步的，getVoices() 一开始返回空，直接 speak() 会等它加载；
 *  - 这里在应用启动时就把声音列表拉好，并在用户第一次交互时做一次静音预热；
 *  - 朗读时显式指定英文声音，避免用默认声音导致更长的准备时间。
 */

let voices = []
let initialized = false
let pendingJobs = []

function refreshVoices() {
  const list = window.speechSynthesis?.getVoices?.() || []
  if (!list.length) return
  voices = list
  const jobs = pendingJobs.splice(0)
  jobs.forEach((fn) => fn())
}

function pickVoice(lang) {
  const normalized = (value) => (value || '').replace('_', '-').toLowerCase()
  return (
    voices.find((v) => normalized(v.lang) === normalized(lang)) ||
    voices.find((v) => normalized(v.lang).startsWith('en')) ||
    null
  )
}

export function initSpeech() {
  if (!('speechSynthesis' in window) || initialized) return
  initialized = true

  refreshVoices()
  window.speechSynthesis.addEventListener('voiceschanged', refreshVoices)

  // 第一次用户交互时读一个静音的空格，把语音引擎唤醒
  const warmUp = () => {
    try {
      const utter = new SpeechSynthesisUtterance(' ')
      utter.volume = 0
      utter.lang = 'en-US'
      window.speechSynthesis.speak(utter)
    } catch {
      /* 忽略 */
    }
    window.removeEventListener('pointerdown', warmUp)
    window.removeEventListener('keydown', warmUp)
  }
  window.addEventListener('pointerdown', warmUp, { once: true })
  window.addEventListener('keydown', warmUp, { once: true })
}

export function speak(text, { lang = 'en-US', rate = 0.9, pitch = 1 } = {}) {
  if (!('speechSynthesis' in window) || !text) return
  const synth = window.speechSynthesis

  if (synth.speaking || synth.pending) synth.cancel()
  if (synth.paused) synth.resume()

  let done = false
  const run = () => {
    if (done) return
    done = true
    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = lang
    utter.rate = rate
    utter.pitch = pitch
    const voice = pickVoice(lang)
    if (voice) utter.voice = voice
    synth.speak(utter)
  }

  if (voices.length) {
    run()
    return
  }

  pendingJobs.push(run)
  refreshVoices()
  // 声音列表一直不来的兜底
  window.setTimeout(() => {
    if (!done && !voices.length) {
      pendingJobs = pendingJobs.filter((fn) => fn !== run)
      run()
    }
  }, 400)
}
