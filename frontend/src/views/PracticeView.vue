<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card head-sticky" style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <div style="font-weight: 700">错题练习</div>
        <div class="muted">
          {{ kpName || '全部知识点' }} · 还剩 {{ remaining }} 题
        </div>
      </div>
      <el-button text class="back-fixed" @click="$router.push('/wrong')">返回</el-button>
    </div>

    <div v-if="loading" class="card">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="done" class="card" style="text-align: center; padding: 40px 20px">
      <div style="font-size: 56px">🌟</div>
      <h2 class="title">这一轮练完了</h2>
      <p class="muted">连对 3 次（每次间隔 ≥10 分钟）的题会移出错题本，并补回 1 朵花。</p>
      <el-button type="primary" size="large" @click="$router.push('/wrong')">
        回错题本
      </el-button>
    </div>

    <div v-else-if="question" class="card">
      <div class="muted" style="margin-bottom: 8px">
        错过 {{ question.error_count }} 次 · 已连对 {{ question.consecutive_correct }}/{{ MASTERY_NEEDED }}
      </div>
      <div class="hint">
        防抢记：同一题两次答对需间隔 {{ COOLDOWN_MINUTES }} 分钟才计下一次连对；连对 {{ MASTERY_NEEDED }} 次会移出错题本并补 1 朵花。
      </div>

      <QuestionRenderer
        :key="question.id"
        :question="question"
        :disabled="submitting"
        @submit="onSubmit"
      />

      <div v-if="feedback" style="margin-top: 20px">
        <el-alert
          :title="feedback.is_correct ? '答对了 ✅' : `答错了，正确答案：${feedback.correct_answer}`"
          :type="feedback.is_correct ? 'success' : 'error'"
          :closable="false"
        />
        <el-alert
          v-if="feedback.is_correct && feedback.counted === false && feedback.cooldown_remaining > 0"
          :title="`答对啦！但距上次答对不足 ${COOLDOWN_MINUTES} 分钟，本次不计入连对（防抢记）。约 ${Math.ceil(feedback.cooldown_remaining / 60)} 分钟后再来可继续累计～`"
          type="warning"
          :closable="false"
          style="margin-top: 10px"
        />
        <el-alert
          v-if="feedback.flower_gained"
          title="补花 +1 🌸 这道题的花已经补回来了！"
          type="success"
          :closable="false"
          style="margin-top: 10px"
        />
        <div v-if="feedback.explanation" class="explain">
          <div class="explain-title">解析</div>
          <div>{{ feedback.explanation }}</div>
        </div>
        <el-alert
          v-if="feedback.mastered"
          title="这道题已经掌握，会从错题本移出"
          type="success"
          :closable="false"
          style="margin-top: 10px"
        />
        <el-button
          type="primary"
          size="large"
          style="width: 100%; margin-top: 16px"
          @click="advance"
        >
          {{ singleMode ? '返回错题本' : '下一题' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import QuestionRenderer from '../components/QuestionRenderer.vue'
import StarField from '../components/StarField.vue'

const route = useRoute()
const router = useRouter()

const MASTERY_NEEDED = 3
const COOLDOWN_MINUTES = 10

const question = ref(null)
const loading = ref(true)
const submitting = ref(false)
const feedback = ref(null)
const remaining = ref(0)
const kpName = ref('')
const done = ref(false)

const kpId = route.query.kp || ''
const scope = route.query.scope || ''
const batchMode = ref(!!scope)
const batchItems = ref([])
const batchIdx = ref(0)
// 单独练一题（从错题本某一行进入）
const singleId = route.query.qid || ''
const singleMode = ref(!!singleId)

onMounted(() => {
  if (batchMode.value) loadBatch()
  else if (singleMode.value) loadOne()
  else next()
})

function newKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '')
  return `${Date.now()}${Math.random().toString(16).slice(2)}`
}

async function next() {
  feedback.value = null
  loading.value = true
  try {
    const { data } = await http.get('/practice/next', {
      params: kpId ? { knowledge_point_id: kpId } : {}
    })
    question.value = data.question
    remaining.value = data.remaining
    kpName.value = data.question.knowledge_point_name
    done.value = false
  } catch (e) {
    const code = e?.response?.data?.detail?.code
    if (code === 'NO_WRONG_QUESTIONS') {
      done.value = true
    } else {
      ElMessage.error(apiError(e))
    }
  } finally {
    loading.value = false
  }
}

async function onSubmit(answer) {
  if (submitting.value || !question.value) return
  submitting.value = true
  try {
    let data
    if (batchMode.value && scope === 'mastered') {
      ;({ data } = await http.post('/practice/recheck', {
        question_id: question.value.id,
        answer
      }))
    } else {
      ;({ data } = await http.post('/practice/result', {
        question_id: question.value.id,
        answer,
        idempotency_key: newKey()
      }))
    }
    feedback.value = data
    remaining.value = Math.max(remaining.value - 1, 0)
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    submitting.value = false
  }
}

async function loadOne() {
  feedback.value = null
  loading.value = true
  try {
    const { data } = await http.get('/practice/one', { params: { question_id: singleId } })
    question.value = data.question
    remaining.value = data.remaining
    kpName.value = data.question.knowledge_point_name
    done.value = false
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}

async function loadBatch() {
  feedback.value = null
  loading.value = true
  try {
    const { data } = await http.get('/practice/batch', {
      params: {
        scope,
        knowledge_point_id: kpId || undefined,
        limit: Number(route.query.limit || 20)
      }
    })
    batchItems.value = data.items || []
    batchIdx.value = 0
    if (!batchItems.value.length) {
      done.value = true
    } else {
      question.value = batchItems.value[0]
      remaining.value = batchItems.value.length
      done.value = false
    }
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}

function advance() {
  feedback.value = null
  if (singleMode.value) {
    router.push('/wrong')
    return
  }
  if (batchMode.value) {
    if (batchIdx.value < batchItems.value.length - 1) {
      batchIdx.value += 1
      question.value = batchItems.value[batchIdx.value]
      remaining.value = batchItems.value.length - batchIdx.value
    } else {
      question.value = null
      done.value = true
    }
  } else {
    next()
  }
}
</script>

<style scoped>
.explain {
  margin-top: 12px;
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.14);
  border-radius: 12px;
  padding: 14px;
  line-height: 1.7;
  font-size: 14px;
  color: var(--wp2-muted);
}
.explain-title {
  font-weight: 800;
  margin-bottom: 6px;
  color: var(--wp2-gold);
}
.hint {
  font-size: 12px;
  color: var(--wp2-dim);
  line-height: 1.5;
  margin-bottom: 10px;
}
</style>
