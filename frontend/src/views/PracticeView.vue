<template>
  <div class="page">
    <div class="card" style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <div style="font-weight: 700">错题练习</div>
        <div class="muted">
          {{ kpName || '全部知识点' }} · 还剩 {{ remaining }} 题
        </div>
      </div>
      <el-button text @click="$router.push('/wrong')">返回</el-button>
    </div>

    <div v-if="loading" class="card">
      <el-skeleton :rows="5" animated />
    </div>

    <div v-else-if="done" class="card" style="text-align: center; padding: 40px 20px">
      <div style="font-size: 56px">🌟</div>
      <h2 class="title">这一轮练完了</h2>
      <p class="muted">答对 2 次的题会从错题本里移出去。</p>
      <el-button type="primary" size="large" @click="$router.push('/wrong')">
        回错题本
      </el-button>
    </div>

    <div v-else-if="question" class="card">
      <div class="muted" style="margin-bottom: 8px">
        错过 {{ question.error_count }} 次 · 已连对 {{ question.consecutive_correct }}/2
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
          @click="next"
        >
          下一题
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import QuestionRenderer from '../components/QuestionRenderer.vue'

const route = useRoute()

const question = ref(null)
const loading = ref(true)
const submitting = ref(false)
const feedback = ref(null)
const remaining = ref(0)
const kpName = ref('')
const done = ref(false)

const kpId = route.query.kp || ''

onMounted(next)

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
    const { data } = await http.post('/practice/result', {
      question_id: question.value.id,
      answer,
      idempotency_key: newKey()
    })
    feedback.value = data
    remaining.value = Math.max(remaining.value - 1, 0)
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.explain {
  margin-top: 12px;
  background: #f8fafc;
  border-radius: 12px;
  padding: 14px;
  line-height: 1.7;
  font-size: 14px;
}
.explain-title {
  font-weight: 700;
  margin-bottom: 6px;
  color: #4c6ef5;
}
</style>
