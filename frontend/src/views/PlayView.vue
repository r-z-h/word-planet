<template>
  <div :class="gameMode ? 'wp-dark v2-page' : 'page'">
    <StarField v-if="gameMode" />
    <SpaceBackdrop v-if="gameMode" />

    <!-- ===== 第二版关卡外壳（玩法 A / B） ===== -->
    <div v-if="gameMode" class="v2-shell">
      <GameHud
        :hearts="heart"
        :combo="combo"
        :level-name="kp?.name"
        :set-no="setNo || 1"
        :set-total="setTotal || 15"
        :done="setDone"
        :segs="segs"
        :flowers="isPurePractice ? null : progress.setFlowers"
        @exit="askExit"
      />
      <div v-if="question" class="v2-body">
        <PlanetEat
          v-if="gameMode === 'planet'"
          ref="planetRef"
          :key="'p-' + question.id"
          :question="question"
          :disabled="submitting || locked"
          :grown="okCount"
          :combo="combo"
          @pick="onPick"
        />
        <LetterBricks
          v-else-if="gameMode === 'bricks'"
          ref="bricksRef"
          :key="'b-' + question.id"
          :question="question"
          :disabled="submitting || locked"
          :wall-words="wallWords"
          @submit="onPick"
        />
        <PipeCatch
          v-else-if="gameMode === 'pipes'"
          ref="pipesRef"
          :key="'c-' + question.id"
          :question="question"
          :disabled="submitting || locked"
          @pick="onPick"
        />
        <MicRead
          v-else
          :key="'d-' + question.id"
          :question="question"
          :disabled="submitting || locked"
          :lit-count="okCount"
          @submit="onPick"
        />
      </div>
      <div v-else class="v2-body">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 答错停住：正确答案 + 音标 + 义项 + 下一题 -->
      <div v-if="feedback" class="v2-feedback">
        <div class="fb-head">
          <div>
            <div class="wp2-dim" style="font-size: 12px">正确答案</div>
            <div class="fb-word">
              <span class="fb-word-text">{{ feedback.word }}</span>
              <span v-if="feedback.phonetic" class="phonetic">{{ feedback.phonetic }}</span>
              <SpeakButton v-if="feedback.word" :text="feedback.word" />
            </div>
          </div>
          <button class="wp2-btn gold" @click="nextAfterFeedback">下一题 →</button>
        </div>
        <div v-if="feedback.senses.length" class="senses">
          <div v-for="(sense, index) in feedback.senses" :key="index" class="sense">
            <span class="index">{{ index + 1 }}</span>
            <span>{{ sense.text }}</span>
            <span v-if="sense.source === 'textbook'" class="tag-textbook">课本</span>
          </div>
        </div>
        <div v-if="feedback.definition_en" class="definition">{{ feedback.definition_en }}</div>
      </div>

      <div v-if="question && !feedback" class="v2-nav">
        <button class="wp2-btn" :disabled="submitting" @click="skipNext">跳过 →</button>
        <span class="wp2-dim" style="font-size: 11.5px">跳过不会记录作答</span>
      </div>
      <div ref="redAlertEl" class="v2-redalert" />
    </div>

    <!-- ===== 第一版布局（其它题型沿用） ===== -->
    <template v-else>
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <div style="font-weight: 700">{{ kp?.name || '加载中' }}</div>
          <div class="muted">
            {{ kp?.level }}<template v-if="setNo"> · 第 {{ setNo }} 套</template>
            <template v-if="setTotal">
              · 第 {{ Math.min(setDone + 1, setTotal) }} / {{ setTotal }} 题
            </template>
            <template v-else> · 还剩 {{ remaining }} 题</template>
          </div>
        </div>
        <el-button text @click="goBack">返回</el-button>
      </div>

      <el-progress
        :percentage="percent"
        :show-text="false"
        :stroke-width="8"
        style="margin-top: 12px"
      />
    </div>

    <div v-if="question" class="card">
      <component
        :is="renderer"
        :key="question.id"
        :question="question"
        :disabled="submitting || locked"
        @submit="onSubmit"
      />
    </div>

    <div v-else class="card">
      <el-skeleton :rows="5" animated />
    </div>

    <!-- 答错停住：正确答案 + 音标 + 全部义项（L3 加英文），点「下一题」才继续 -->
    <div v-if="feedback" class="card feedback">
      <div class="fb-head">
        <div>
          <div class="muted">正确答案</div>
          <div class="fb-word">
            <span class="fb-word-text">{{ feedback.word }}</span>
            <span v-if="feedback.phonetic" class="phonetic">{{ feedback.phonetic }}</span>
            <SpeakButton v-if="feedback.word" :text="feedback.word" />
          </div>
        </div>
        <el-button type="primary" size="large" @click="nextAfterFeedback">下一题</el-button>
      </div>

      <div v-if="feedback.senses.length" class="senses">
        <div v-for="(sense, index) in feedback.senses" :key="index" class="sense">
          <span class="index">{{ index + 1 }}</span>
          <span>{{ sense.text }}</span>
          <el-tag
            v-if="sense.source === 'textbook'"
            size="small"
            type="warning"
            effect="plain"
            style="margin-left: 6px"
          >
            课本
          </el-tag>
        </div>
      </div>

      <div v-if="feedback.definition_en" class="definition">{{ feedback.definition_en }}</div>
    </div>

    <div v-if="question && !feedback" class="nav-row">
      <el-button :disabled="!history.length || submitting" @click="goPrev">← 上一题</el-button>
      <span class="muted small">跳过不会记录作答</span>
      <el-button :disabled="submitting" @click="skipNext">下一题 →</el-button>
    </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { onBeforeRouteLeave, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { apiError } from '../api/http'
import { useProgressStore } from '../stores/progress'
import QuestionRenderer from '../components/QuestionRenderer.vue'
import PronunciationGame from '../components/PronunciationGame.vue'
import SpeakButton from '../components/SpeakButton.vue'
import StarField from '../components/StarField.vue'
import GameHud from '../components/game/GameHud.vue'
import PlanetEat from '../components/game/PlanetEat.vue'
import LetterBricks from '../components/game/LetterBricks.vue'
import PipeCatch from '../components/game/PipeCatch.vue'
import MicRead from '../components/game/MicRead.vue'
import SpaceBackdrop from '../components/game/SpaceBackdrop.vue'
import { sfxDing, sfxBuzz } from '../utils/sfx'

const router = useRouter()
const progress = useProgressStore()

const kp = ref(null)
const question = ref(null)
const submitting = ref(false)
const locked = ref(false)
const feedback = ref(null)
const advancedPending = ref(null)
const pronMode = ref(false)
const leavingByResult = ref(false)
const history = ref([])
const setNo = ref(null)
const setTotal = ref(0)
const setDone = ref(0)

// ===== 第二版关卡状态 =====
const planetRef = ref(null)
const bricksRef = ref(null)
const pipesRef = ref(null)
const redAlertEl = ref(null)
const okCount = ref(0) // 本关已答对题数（驱动养成）
const combo = ref(0) // 连击（驱动四档动作 / 连击显示）
const heart = ref(3) // 命（纯视觉）
const segs = ref([]) // 15 段路段条：'ok' | 'no'
const wallWords = ref([]) // 玩法 B 的单词墙（拼对过的词）

const remaining = computed(() => progress.todayTask?.target_count ?? 0)
const percent = computed(() => {
  if (!setTotal.value) return 0
  return Math.min(100, Math.round((setDone.value / setTotal.value) * 100))
})
const renderer = computed(() => (pronMode.value ? PronunciationGame : QuestionRenderer))

// 当前题走哪个第二版玩法：planet(letter/word) | bricks(spelling) | null(沿用第一版)
const gameMode = computed(() => {
  if (!question.value) return null
  if (pronMode.value) return 'mic'
  const t = question.value.question_type
  if (t === 'letter' || t === 'word') return 'planet'
  if (t === 'spelling') return 'bricks'
  if (t === 'listening') return 'pipes'
  return null
})
// 纯练星球（字母表/听力）：不显示花计数
const isPurePractice = computed(
  () => !!question.value && ['letter', 'listening'].includes(question.value.question_type)
)

function onPick(payload) {
  onSubmit(payload)
}

// 关卡内退出：交给路由守卫统一确认「保存并返回 / 继续做题」
function askExit() {
  router.replace('/home')
}

// 玩法 C 答错：全屏红警闪一下 + 整页晃动
function flashRedAlert() {
  const el = redAlertEl.value
  if (el) {
    el.classList.remove('on')
    void el.offsetWidth
    el.classList.add('on')
  }
  const shell = document.querySelector('.v2-shell')
  if (shell) {
    shell.classList.remove('shakeall')
    void shell.offsetWidth
    shell.classList.add('shakeall')
    setTimeout(() => shell.classList.remove('shakeall'), 560)
  }
}

onMounted(load)

async function load() {
  try {
    await progress.fetchProgress()
    kp.value = progress.currentKnowledgePoint
    if (!kp.value) {
      ElMessage.warning('还没有当前知识点，请先完成水平测试')
      return
    }
    pronMode.value = kp.value.question_type === 'pronunciation'
    await next()
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function next(excludeId = '') {
  locked.value = false
  feedback.value = null
  try {
    const url = pronMode.value ? '/pronunciation/next' : '/question/next'
    const excluded = [...history.value.map((q) => q.id), excludeId].filter(Boolean)
    const params = excluded.length ? { exclude_id: excluded.join(',') } : {}
    const { data } = await http.get(url, { params })
    question.value = data.question
    // 玩法 C（听力）按「每题 3 次机会」算：进新题重置心
    if (data.question?.question_type === 'listening') heart.value = 3
    if (data.set_no) {
      setNo.value = data.set_no
      setTotal.value = data.set_total
      setDone.value = data.set_done
    }
  } catch (e) {
    const code = e?.response?.data?.detail?.code
    if (code === 'KNOWLEDGE_POINT_FINISHED' || code === 'SET_FINISHED') {
      ElMessage.success('这个模块已经学完了，去试试别的星球吧')
      router.replace('/home')
      return
    }
    ElMessage.error(apiError(e))
  }
}
function skipNext() {
  if (!question.value) return
  const current = question.value
  history.value.push(current)
  next(current.id)
}

function goPrev() {
  if (!history.value.length) return
  locked.value = false
  feedback.value = null
  question.value = history.value.pop()
}

function forgetInHistory(questionId) {
  history.value = history.value.filter((q) => q.id !== questionId)
}

function newKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '')
  return `${Date.now()}${Math.random().toString(16).slice(2)}`
}

async function onSubmit(payload) {
  if (submitting.value || locked.value || !question.value) return
  submitting.value = true
  locked.value = true
  const finishedName = kp.value?.name || ''
  const finishedSet = setNo.value
  const answeredId = question.value.id
  // 选择题记下选了哪个键（玩法 C 要标出是哪条管道）
  const pickedAnswer = typeof payload === 'string' ? payload.toUpperCase() : payload

  try {
    let advanced = false
    let correct = false
    let detail = null

    if (pronMode.value) {
      const { data } = await http.post('/pronunciation/result', {
        word_id: question.value.id,
        is_correct: payload.is_correct,
        idempotency_key: newKey()
      })
      advanced = data.progress_advanced
      correct = Boolean(payload.is_correct)
      detail = data
      if (correct) ElMessage.success('读得不错')
      else ElMessage.warning('再来一次，已经记进错题本了')
    } else {
      const data = await progress.submitAnswer(question.value.id, payload, newKey())
      advanced = data.progress_advanced
      correct = data.is_correct
      detail = data
      if (correct) ElMessage.success('答对了')
      else ElMessage.error('答错了，已放进错题本')
    }

    // 第二版关卡音效（所有玩法统一）
    if (gameMode.value) {
      if (correct) sfxDing()
      else sfxBuzz()
    }

    await progress.fetchProgress()
    forgetInHistory(answeredId)
    submitting.value = false

    const isPipes = gameMode.value === 'pipes'

    // ===== 玩法 C：答错可重试（最多 3 次，扣光心后揭晓答案） =====
    if (isPipes && !correct) {
      combo.value = 0
      heart.value = Math.max(0, heart.value - 1)
      pipesRef.value?.markResult(pickedAnswer, false)
      flashRedAlert()
      if (heart.value > 0) {
        // 还能再试：解锁，保持同一题（可先重听）
        locked.value = false
        ElMessage.warning(detail?.answer_text ? '再听一次，仔细选' : '再试一次')
        return
      }
      // 三次错完：揭晓正确答案 → 2 秒后下一题
      pipesRef.value?.revealAnswer(detail?.answer_text || '')
      segs.value.push('no')
      setDone.value = Math.min(setDone.value + 1, setTotal.value)
      heart.value = 3
      ElMessage.warning(`正确答案是 ${detail?.answer_text || ''}`)
      const pendingSet = advanced ? { set: finishedSet, kp: finishedName } : null
      setTimeout(() => {
        locked.value = false
        if (pendingSet) {
          leavingByResult.value = true
          router.replace({
            path: '/result',
            query: { set: String(pendingSet.set || ''), kp: pendingSet.kp }
          })
          return
        }
        next()
      }, 2000)
      return
    }

    setDone.value = Math.min(setDone.value + 1, setTotal.value)

    // ===== 第二版关卡：局内养成 + 连击 + 路段条 =====
    if (gameMode.value) {
      if (correct) {
        combo.value += 1
        okCount.value += 1
        segs.value.push('ok')
        if (gameMode.value === 'planet') planetRef.value?.celebrate(combo.value)
        if (gameMode.value === 'bricks') {
          bricksRef.value?.markResult(true)
          const w = detail?.answer_text || ''
          if (w) wallWords.value.push(w)
        }
        if (gameMode.value === 'pipes') pipesRef.value?.markResult(pickedAnswer, true)
      } else {
        combo.value = 0
        heart.value = Math.max(0, heart.value - 1)
        segs.value.push('no')
        if (gameMode.value === 'bricks') bricksRef.value?.markResult(false)
      }
    }

    if (advanced) {
      // 整套学完了：答对直接进结算页；答错先把义项看完，点「下一题」再进结算页
      if (correct) {
        leavingByResult.value = true
        router.replace({
          path: '/result',
          query: { set: String(finishedSet || ''), kp: finishedName }
        })
        return
      }
      advancedPending.value = { set: finishedSet, kp: finishedName }
    }

    if (correct) {
      // 答对保持自动跳（玩法 A 留足吞卡/成长动画时间）
      setTimeout(() => {
        next()
      }, gameMode.value ? 900 : 250)
      return
    }

    // 答错停住：展示正确答案、音标、全部义项
    feedback.value = {
      word: detail?.word?.word || detail?.answer_text || '',
      phonetic: detail?.word?.phonetic || '',
      senses: detail?.word?.senses || [],
      definition_en: detail?.word?.definition_en || null
    }
  } catch (e) {
    ElMessage.error(apiError(e))
    submitting.value = false
    locked.value = false
  }
}

function nextAfterFeedback() {
  const pending = advancedPending.value
  feedback.value = null
  locked.value = false
  if (pending) {
    leavingByResult.value = true
    router.replace({
      path: '/result',
      query: { set: String(pending.set || ''), kp: pending.kp }
    })
    return
  }
  next()
}

function goBack() {
  router.push('/home')
}

// 有题没做完就离开时要提示；进度与当前题都在服务端，下次进来会恢复到这一题
onBeforeRouteLeave(async () => {
  // 已答过（正在看义项面板）或已经跳结算页时不需要再拦
  if (leavingByResult.value || !question.value || feedback.value) return true
  try {
    await ElMessageBox.confirm(
      '这道题还没做完。确定要返回吗？学习记录会保存，下次点“继续学习”会回到这道题。',
      '还有题目没完成',
      { confirmButtonText: '保存并返回', cancelButtonText: '继续做题', type: 'warning' }
    )
    return true
  } catch {
    return false
  }
})
</script>

<style scoped>
.nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 4px 8px;
}
.nav-row .small {
  font-size: 12px;
}
.feedback .fb-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.fb-word {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-top: 2px;
}
.fb-word-text {
  font-size: 22px;
  font-weight: 700;
}
.phonetic {
  color: #64748b;
  font-size: 13px;
}
.senses {
  margin-top: 12px;
}
.sense {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 15px;
  line-height: 1.8;
  color: #334155;
}
.index {
  color: #94a3b8;
  font-size: 12px;
  min-width: 14px;
}
.definition {
  margin-top: 10px;
  background: #f8fafc;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
  white-space: pre-line;
}

/* ===== 第二版玩法 A 外壳 ===== */
.v2-page {
  min-height: 100vh;
  padding: 0;
  max-width: none;
}
.v2-shell {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 14px 14px;
  user-select: none;
  -webkit-user-select: none;
  -webkit-touch-callout: none;
}
.v2-body {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 10px 0;
}
.v2-nav {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 6px 0;
}
.v2-feedback {
  flex: none;
  background: var(--wp2-panel);
  border: 2px solid rgba(255, 226, 168, 0.22);
  border-radius: 16px;
  padding: 14px 16px;
  margin-top: 8px;
}
.v2-feedback .fb-word-text {
  color: var(--wp2-ink);
}
.v2-feedback .phonetic {
  color: var(--wp2-muted);
}
.v2-feedback .sense {
  color: var(--wp2-muted);
}
.v2-feedback .index {
  color: var(--wp2-dim);
}
.v2-feedback .definition {
  background: rgba(255, 246, 225, 0.06);
  color: var(--wp2-muted);
}
.tag-textbook {
  margin-left: 6px;
  font-size: 11px;
  font-weight: 800;
  color: var(--wp2-gold);
  border: 1.5px solid rgba(255, 205, 76, 0.6);
  border-radius: 99px;
  padding: 1px 7px;
}

/* 玩法 C 答错：全屏红警 + 整页晃动 */
.v2-redalert {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 60;
  opacity: 0;
  box-shadow: inset 0 0 0 6px rgba(255, 60, 60, 0.9), inset 0 0 80px rgba(255, 40, 40, 0.6);
  background: rgba(255, 40, 40, 0.16);
}
.v2-redalert.on { animation: v2-redalert 1s ease-out; }
@keyframes v2-redalert {
  0% { opacity: 0; }
  12% { opacity: 1; }
  30% { opacity: 0.4; }
  46% { opacity: 1; }
  64% { opacity: 0.35; }
  80% { opacity: 0.9; }
  100% { opacity: 0; }
}
.v2-shell.shakeall { animation: v2-bigshake 0.5s ease-in-out; }
.v2-shell.fx-shake { animation: fx-shake-kf 0.42s ease-in-out; }
@keyframes fx-shake-kf {
  0%, 100% { transform: translate(0, 0); }
  20% { transform: translate(-5px, 2px); }
  40% { transform: translate(5px, -2px); }
  60% { transform: translate(-4px, -1px); }
  80% { transform: translate(4px, 1px); }
}
@keyframes v2-bigshake {
  0%, 100% { transform: translate(0, 0); }
  10% { transform: translate(-10px, 4px); }
  20% { transform: translate(10px, -4px); }
  30% { transform: translate(-9px, -3px); }
  40% { transform: translate(9px, 3px); }
  50% { transform: translate(-7px, 2px); }
  60% { transform: translate(7px, -2px); }
  70% { transform: translate(-5px, 0); }
  80% { transform: translate(5px, 0); }
  90% { transform: translate(-2px, 0); }
}
@media (prefers-reduced-motion: reduce) {
  .v2-shell.shakeall { animation: none; }
  .v2-shell.fx-shake { animation: none; }
  .v2-redalert.on { animation: none; opacity: 0; }
}
</style>
