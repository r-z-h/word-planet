/**
 * 统一的语音合成封装。
 *
 * 关键点：
 *  1. 浏览器加载声音列表是异步的，第一次 speak 会等它 —— 启动时先拉一次。
 *  2. Edge 上声音很多（本地 Zira / 在线 Natural / 各种口音），随便挑一个会
 *     既慢又读错。这里按「本地优先、英音优先、名字可信」打分选声。
 *  3. 在线声音（名字里带 Online / Natural）需要联网，国内网络下会卡几秒，
 *     所以默认降权，只有没有本地英文声音时才用。
 */

let voices = []
let initialized = false
let pendingJobs = []

function normalizeLang(value) {
  return (value || '').replace('_', '-').toLowerCase()
}

function refreshVoices() {
  const list = window.speechSynthesis?.getVoices?.() || []
  if (!list.length) return
  const firstLoad = voices.length === 0
  voices = list
  if (firstLoad && window.console) {
    const english = voices.filter((v) => normalizeLang(v.lang).startsWith('en'))
    console.info(
      '[speech] 英文声音共',
      english.length,
      '个，将使用：',
      pickVoice()?.name || '(无可用英文声音)'
    )
    console.info(
      '[speech] 全部英文声音：',
      english.map((v) => `${v.name} (${v.lang}${v.localService ? ', 本地' : ', 在线'})`)
    )
  }
  const jobs = pendingJobs.splice(0)
  jobs.forEach((fn) => fn())
}

const GOOD_NAMES = /zira|aria|jenny|guy|sonia|ryan|libby|natasha|david|mark|hazel|susan|george/i
const ONLINE_NAMES = /online|natural/i

function scoreVoice(voice) {
  const lang = normalizeLang(voice.lang)
  if (!lang.startsWith('en')) return -1

  let score = 0
  // 本地声音：不联网，响应快，读音稳定
  if (voice.localService) score += 20
  // 在线声音要联网，国内网络下容易卡
  if (ONLINE_NAMES.test(voice.name || '')) score -= 8

  if (lang === 'en-us') score += 5
  else if (lang === 'en-gb') score += 4
  else score += 1

  if (GOOD_NAMES.test(voice.name || '')) score += 3
  return score
}

export function listEnglishVoices() {
  return voices
    .filter((v) => normalizeLang(v.lang).startsWith('en'))
    .map((v) => ({
      name: v.name,
      lang: v.lang,
      local: Boolean(v.localService),
      score: scoreVoice(v)
    }))
    .sort((a, b) => b.score - a.score)
}

function pickVoice() {
  let best = null
  let bestScore = 0
  for (const voice of voices) {
    const score = scoreVoice(voice)
    if (score > bestScore) {
      best = voice
      bestScore = score
    }
  }
  return best
}

export function initSpeech() {
  if (!('speechSynthesis' in window) || initialized) return
  initialized = true

  refreshVoices()
  window.speechSynthesis.addEventListener('voiceschanged', refreshVoices)

  // 第一次用户交互时读一个静音空格，把语音引擎唤醒
  const warmUp = () => {
    try {
      const utter = new SpeechSynthesisUtterance(' ')
      utter.volume = 0
      utter.lang = 'en-US'
      const voice = pickVoice()
      if (voice) utter.voice = voice
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

  let done = false
  const run = () => {
    if (done) return
    done = true
    const utter = new SpeechSynthesisUtterance(text)
    utter.lang = lang
    utter.rate = rate
    utter.pitch = pitch
    utter.volume = 1
    const voice = pickVoice()
    if (voice) {
      utter.voice = voice
      utter.lang = voice.lang || lang
    }
    synth.speak(utter)
  }

  if (voices.length) {
    run()
    return
  }

  pendingJobs.push(run)
  refreshVoices()
  window.setTimeout(() => {
    if (!done && !voices.length) {
      pendingJobs = pendingJobs.filter((fn) => fn !== run)
      run()
    }
  }, 400)
}
