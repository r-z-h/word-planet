<template>
  <div class="page">
    <div class="card">
      <h2 class="title">先做个小测试 🌍</h2>
      <p class="muted">共 10 题左右，答完就能找到适合你的起点。</p>
      <el-progress
        :percentage="Math.round(((index - 1) / 10) * 100)"
        :show-text="false"
        style="margin-top: 12px"
      />
      <div class="muted" style="margin-top: 8px">第 {{ index }} 题</div>
    </div>

    <div v-if="question" class="card">
      <QuestionRenderer
        :key="question.id"
        :question="question"
        :disabled="submitting"
        @submit="onAnswer"
      />
    </div>

    <div v-else class="card">
      <el-skeleton :rows="4" animated />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import QuestionRenderer from '../components/QuestionRenderer.vue'
import { useUserStore } from '../stores/user'

const router = useRouter()
const user = useUserStore()

const question = ref(null)
const index = ref(1)
const submitting = ref(false)

onMounted(start)

async function start() {
  try {
    const { data } = await http.post('/test/start')
    question.value = data.question
    index.value = data.question_index || 1
  } catch (e) {
    ElMessage.error(apiError(e))
    router.replace('/home')
  }
}

async function onAnswer(answer) {
  if (submitting.value || !question.value) return
  submitting.value = true
  try {
    const { data } = await http.post('/test/answer', {
      question_id: question.value.id,
      answer
    })
    if (data.is_finished) {
      user.setLevel(data.level)
      ElMessage.success(`测试完成，你的起点是 ${data.level}`)
      router.replace('/home')
      return
    }
    index.value += 1
    question.value = data.next_question
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    submitting.value = false
  }
}
</script>
