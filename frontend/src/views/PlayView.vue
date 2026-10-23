<template>
  <div class="page">
    <div class="card" style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <div style="font-weight: 700">{{ kp?.name || '加载中' }}</div>
        <div class="muted">{{ kp?.level }} · 还剩 {{ progress.todayTask.target_count }} 题</div>
      </div>
      <el-button text @click="$router.push('/home')">返回</el-button>
    </div>

    <div v-if="celebrating" class="card" style="text-align: center">
      <div style="font-size: 48px">🎉</div>
      <h2 class="title">这个知识点学完啦！</h2>
      <p class="muted">已经解锁下一个知识点，明天继续加油。</p>
      <el-button type="primary" size="large" @click="$router.push('/home')">回首页</el-button>
    </div>

    <div v-else-if="question" class="card">
      <component
        :is="renderer"
        :key="question.id"
        :question="question"
        :disabled="loading"
        @submit="onSubmit"
      />

      <div v-if="feedback" style="margin-top: 20px">
        <el-alert
          :title="feedback.is_correct ? '答对啦 ✅' : `再想想：正确答案是 ${feedback.correct_answer}`"
          :type="feedback.is_correct ? 'success' : 'error'"
          :closable="false"
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

    <div v-else class="card">
      <el-skeleton :rows="5" animated />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useProgressStore } from '../stores/progress'
import QuestionRenderer from '../components/QuestionRenderer.vue'
import PronunciationGame from '../components/PronunciationGame.vue'

const progress = useProgressStore()

const kp = ref(null)
const question = ref(null)
const feedback = ref(null)
const loading = ref(false)
const celebrating = ref(false)
const pronMode = ref(false)

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

async function next() {
  feedback.value = null
  try {
    const url = pronMode.value ? '/pronunciation/next' : '/question/next'
    const { data } = await http.get(url)
    question.value = data.question
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function newKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '')
  return `${Date.now()}${Math.random().toString(16).slice(2)}`
}

async function onSubmit(payload) {
  if (loading.value || !question.value) return
  loading.value = true
  try {
    if (pronMode.value) {
      const { data } = await http.post('/pronunciation/result', {
        word_id: question.value.id,
        is_correct: payload.is_correct,
        idempotency_key: newKey()
      })
      feedback.value = {
        is_correct: payload.is_correct,
        correct_answer: question.value.answer
      }
      if (data.progress_advanced) {
        celebrating.value = true
        await progress.fetchProgress()
      }
    } else {
      const data = await progress.submitAnswer(question.value.id, payload, newKey())
      feedback.value = data
      if (data.progress_advanced) {
        celebrating.value = true
        await progress.fetchProgress()
        kp.value = progress.currentKnowledgePoint
      }
      if (data.new_badges?.length) {
        ElMessage.success('解锁新徽章！')
      }
    }
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}
</script>
