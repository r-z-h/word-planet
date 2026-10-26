<template>
  <div class="page">
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

const remaining = computed(() => progress.todayTask?.target_count ?? 0)
const percent = computed(() => {
  if (!setTotal.value) return 0
  return Math.min(100, Math.round((setDone.value / setTotal.value) * 100))
})
const renderer = computed(() => (pronMode.value ? PronunciationGame : QuestionRenderer))

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
    if (data.set_no) {
      setNo.value = data.set_no
      setTotal.value = data.set_total
      setDone.value = data.set_done
    }
  } catch (e) {
    const code = e?.response?.data?.detail?.code
    if (code === 'KNOWLEDGE_POINT_FINISHED' || code === 'SET_FINISHED') {
      ElMessage.success('这个模块已经学完了，去试试别的模块吧')
      router.replace('/modules')
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

    await progress.fetchProgress()
    forgetInHistory(answeredId)
    setDone.value = Math.min(setDone.value + 1, setTotal.value)
    submitting.value = false

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
      // 答对保持自动跳
      setTimeout(() => {
        next()
      }, 250)
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
</style>
