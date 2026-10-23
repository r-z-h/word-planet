<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <div style="font-weight: 700">{{ kp?.name || '加载中' }}</div>
          <div class="muted">
            {{ kp?.level }} ·
            <template v-if="progress.kpTotal">
              第 {{ Math.min(progress.kpDone + 1, progress.kpTotal) }} / {{ progress.kpTotal }} 题
            </template>
            <template v-else>还剩 {{ remaining }} 题</template>
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
        :disabled="submitting"
        @submit="onSubmit"
      />
    </div>

    <div v-else class="card">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-if="!pronMode && question" class="nav-row">
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

const router = useRouter()
const progress = useProgressStore()

const kp = ref(null)
const question = ref(null)
const submitting = ref(false)
const pronMode = ref(false)
const leavingByResult = ref(false)
const history = ref([])

const remaining = computed(() => progress.todayTask?.target_count ?? 0)
const percent = computed(() => {
  if (!progress.kpTotal) return 0
  return Math.min(100, Math.round((progress.kpDone / progress.kpTotal) * 100))
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
  try {
    const url = pronMode.value ? '/pronunciation/next' : '/question/next'
    const params = excludeId ? { exclude_id: excludeId } : {}
    const { data } = await http.get(url, { params })
    question.value = data.question
  } catch (e) {
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
  if (submitting.value || !question.value) return
  submitting.value = true
  const finishedName = kp.value?.name || ''
  const answeredId = question.value.id

  try {
    let advanced = false

    if (pronMode.value) {
      const { data } = await http.post('/pronunciation/result', {
        word_id: question.value.id,
        is_correct: payload.is_correct,
        idempotency_key: newKey()
      })
      advanced = data.progress_advanced
      if (payload.is_correct) ElMessage.success('读得不错')
      else ElMessage.warning('再来一次，已经记进错题本了')
    } else {
      const data = await progress.submitAnswer(question.value.id, payload, newKey())
      advanced = data.progress_advanced
      if (data.is_correct) ElMessage.success('答对了')
      else ElMessage.error('答错了，已放进错题本')
    }

    await progress.fetchProgress()
    forgetInHistory(answeredId)

    if (advanced) {
      leavingByResult.value = true
      router.replace({ path: '/result', query: { finished: finishedName } })
      return
    }

    setTimeout(() => {
      submitting.value = false
      next()
    }, 250)
  } catch (e) {
    ElMessage.error(apiError(e))
    submitting.value = false
  }
}

function goBack() {
  router.push('/home')
}

// 有题没做完就离开时要提示；进度与当前题都在服务端，下次进来会恢复到这一题
onBeforeRouteLeave(async () => {
  if (leavingByResult.value || !question.value) return true
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
</style>
