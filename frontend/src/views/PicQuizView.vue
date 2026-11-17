<template>
  <div class="pq wp-dark">
    <StarField />
    <el-button text class="back-fixed" @click="$router.push('/home')">返回</el-button>
    <header class="pq-head">
      <h1>🔍 看图猜词</h1>
      <div v-if="phase === 'play'" class="pq-score">得分 {{ score }} · 连对 {{ streak }}</div>
    </header>

    <main class="pq-body">
      <div v-if="loading" class="pq-tip">加载中…</div>
      <div v-else-if="loadError" class="pq-tip">{{ loadError }}</div>

      <div v-else-if="phase === 'pick'" class="pq-pick">
        <p class="pq-hint">选一个主题开始 · 本套全部答对 = 满星完成 = 1 枚徽记</p>
        <div class="pq-cats">
          <button v-for="c in cats" :key="c.set_no" class="pq-cat" @click="start(c.set_no)">
            <img :src="c.cover" alt="" />
            <span class="cn">{{ c.catCn }}</span>
            <span class="num">{{ c.count }} 个词</span>
          </button>
        </div>
      </div>

      <div v-else-if="phase === 'play' && show" class="pq-quiz">
        <div class="pq-meta">已答对 {{ mastered }} / {{ total }} 题（答错会排到后面重做）</div>
        <div class="pq-imgwrap"><img :src="show.img" alt="" /></div>
        <div class="pq-opts">
          <button v-for="o in show.options" :key="o" class="pq-opt" :class="optClass(o)" :disabled="locked" @click="choose(o)">{{ o }}</button>
        </div>
        <div v-if="feedback" class="pq-fb">{{ feedback }}</div>
      </div>

      <div v-else-if="phase === 'done'" class="pq-done">
        <div class="pq-stars">★★★</div>
        <div class="pq-big">{{ total }} / {{ total }}</div>
        <div class="pq-sub">本套全部答对 · 得 1 枚徽记 · 得分 {{ score }}</div>
        <div class="pq-btns">
          <button class="pq-btn gold" @click="start(curSet)">再玩一次</button>
          <button class="pq-btn" @click="phase = 'pick'">换主题</button>
          <button class="pq-btn" @click="goHome">返回首页</button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import StarField from '../components/StarField.vue'
import http from '../api/http'

const router = useRouter()
const loading = ref(true)
const loadError = ref('')
const phase = ref('pick')
const cats = ref([])
const questionsAll = ref([])
const queue = ref([])
const show = ref(null)
const total = ref(0)
const mastered = ref(0)
const curSet = ref(0)
const score = ref(0)
const streak = ref(0)
const locked = ref(false)
const feedback = ref('')
const picked = ref('')
const wordFile = {}
const SET_NAMES = ['人物/职业', '动物', '食物/饮料', '身体部位', '文具/教室', '场所/房间', '衣物', '物品/玩具', '天气']

function imgOf(word) {
  return wordFile[word] || ''
}

onMounted(async () => {
  try {
    const [qr, mr] = await Promise.all([
      http.get('/picquiz/questions'),
      fetch('/picquiz_imgs/manifest.json').then((r) => r.json())
    ])
    for (const it of mr) wordFile[it.word] = '/picquiz_imgs/' + it.file
    const qs = (qr.data.questions || []).map((q) => ({
      id: q.id,
      set_no: q.set_no,
      word: q.word,
      cn: q.cn,
      options: q.options || [],
      img: imgOf(q.word)
    }))
    questionsAll.value = qs
    cats.value = (qr.data.sets || []).map((s) => {
      const first = qs.find((q) => q.set_no === s.set_no)
      return { set_no: s.set_no, count: s.count, catCn: SET_NAMES[s.set_no - 1] || '主题', cover: first ? imgOf(first.word) : '' }
    })
    if (!qs.length) loadError.value = '看图猜词题目还没初始化（请先运行 seed_picquiz.py 并重启后端）'
  } catch (e) {
    loadError.value = '加载失败：' + (e && e.message ? e.message : e)
  }
  loading.value = false
})

function shuffle(a) {
  for (let i = a.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}
function start(setNo) {
  curSet.value = setNo
  phase.value = 'play'
  score.value = 0
  mastered.value = 0
  streak.value = 0
  locked.value = false
  feedback.value = ''
  picked.value = ''
  queue.value = shuffle(questionsAll.value.filter((q) => q.set_no === setNo).map((q) => ({ ...q })))
  total.value = queue.value.length
  show.value = queue.value[0] || null
}
async function choose(o) {
  if (locked.value || !show.value) return
  locked.value = true
  picked.value = o
  const q = show.value
  let ok = false
  try {
    const { data } = await http.post('/picquiz/answer', { question_id: q.id, answer: o })
    ok = !!data.is_correct
    if (ok) {
      mastered.value += 1
      score.value += 10 + streak.value * 2
      streak.value += 1
      feedback.value = '✅ 答对了！' + data.word + ' ' + data.cn
      speak(data.word)
      queue.value.shift()
    } else {
      streak.value = 0
      feedback.value = '❌ 正确答案：' + data.word + ' ' + data.cn + '（稍后再做这道）'
      queue.value.push(queue.value.shift()) // 答错排到队尾重做
    }
  } catch (e) {
    feedback.value = '提交失败：' + (e && e.message ? e.message : e)
    // 失败也排到后面，避免卡死
    queue.value.push(queue.value.shift())
  }
  setTimeout(() => {
    locked.value = false
    picked.value = ''
    feedback.value = ''
    if (queue.value.length) show.value = queue.value[0]
    else phase.value = 'done'
  }, 850)
}
function optClass(o) {
  if (!locked.value || !show.value) return ''
  if (o === show.value.word) return 'right'
  if (o === picked.value) return 'wrong'
  return ''
}
function speak(w) {
  try {
    const u = new SpeechSynthesisUtterance(w)
    u.lang = 'en-US'
    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(u)
  } catch {
    /* ignore */
  }
}
function goHome() {
  router.push('/home')
}
</script>

<style scoped>
.pq { min-height: 100vh; background: var(--wp2-grad); color: var(--wp2-ink); display: flex; flex-direction: column; position: relative; }
.pq-head { display: flex; align-items: center; gap: 14px; padding: 14px 20px; }
.pq-back { background: rgba(255,255,255,.12); border: 0; color: #eef; border-radius: 10px; padding: 8px 14px; cursor: pointer; font-size: 14px; }
.pq-head h1 { font-size: 20px; margin: 0; }
.pq-score { margin-left: auto; font-weight: 800; color: #ffd76e; }
.pq-body { flex: 1; display: flex; justify-content: center; padding: 10px 16px 30px; }
.pq-tip { color: #b9b3d6; margin-top: 40px; }
.pq-pick { width: 100%; max-width: 980px; }
.pq-hint { color: #b9b3d6; text-align: center; margin: 6px 0 18px; }
.pq-cats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
.pq-cat { background: rgba(255,255,255,.06); border: 1px solid rgba(255,255,255,.12); border-radius: 16px; padding: 14px; color: #eef; cursor: pointer; display: flex; flex-direction: column; align-items: center; gap: 4px; }
.pq-cat:hover { background: rgba(255,255,255,.12); }
.pq-cat img { width: 84px; height: 84px; object-fit: contain; }
.pq-cat .cn { font-weight: 800; font-size: 15px; }
.pq-cat .num { font-size: 12px; color: #b9b3d6; }
.pq-quiz { width: 100%; max-width: 720px; display: flex; flex-direction: column; align-items: center; }
.pq-meta { color: #b9b3d6; margin-bottom: 8px; }
.pq-imgwrap { width: 320px; height: 320px; border-radius: 20px; background: #fff; display: grid; place-items: center; margin-bottom: 18px; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
.pq-imgwrap img { width: 88%; height: 88%; object-fit: contain; }
.pq-opts { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; width: 100%; max-width: 560px; }
.pq-opt { padding: 16px; border-radius: 14px; font-size: 18px; font-weight: 800; background: rgba(255,255,255,.1); color: #eef; border: 2px solid transparent; cursor: pointer; }
.pq-opt:hover:not(:disabled) { background: rgba(255,255,255,.18); }
.pq-opt.right { background: #2ecc71; border-color: #27ae60; }
.pq-opt.wrong { background: #e74c3c; border-color: #c0392b; }
.pq-fb { margin-top: 16px; font-size: 16px; font-weight: 700; min-height: 24px; }
.pq-done { text-align: center; margin-top: 30px; }
.pq-stars { font-size: 44px; color: #ffd76e; letter-spacing: 6px; }
.pq-big { font-size: 40px; font-weight: 900; margin: 8px 0; }
.pq-sub { color: #b9b3d6; margin-bottom: 22px; }
.pq-btns { display: flex; gap: 12px; justify-content: center; }
.pq-btn { padding: 12px 22px; border-radius: 12px; border: 0; cursor: pointer; font-weight: 800; background: rgba(255,255,255,.12); color: #eef; }
.pq-btn.gold { background: #ffd76e; color: #5a3a00; }
@media (max-width: 640px) { .pq-cats { grid-template-columns: repeat(2, 1fr); } .pq-imgwrap { width: 72vw; height: 72vw; } .pq-opts { grid-template-columns: 1fr; } }
</style>
