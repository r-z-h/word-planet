<template>
  <div class="page">
    <div class="card" style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <div style="font-weight: 700">{{ kp?.name || '加载中' }}</div>
        <div class="muted">{{ kp?.level }} · 还剩 {{ remaining }} 题</div>
      </div>
      <el-button text @click="goBack">返回</el-button>
    </div>

    <div v-if="celebrating" class="card" style="text-align: center">
      <div style="font-size: 48px">🎉</div>
      <h2 class="title">这个知识点学完啦！</h2>
      <p class="muted">已经解锁下一个知识点，明天继续加油。</p>
      <el-button type="primary" size="large" @click="leaveToHome">回首页</el-button>
    </div>

    <div v-else-if="question" class="card">
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
const celebrating = ref(false)
const pronMode = ref(false)

const remaining = computed(() => progress.todayTask?.target_count ?? 0)
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
  if (submitting.value || !question.value) return
  submitting.value = true
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
      if (data.is_correct) {
        ElMessage.success('答对了')
      } else {
        // 按需求：答错不显示正确答案，直接进下一题
        ElMessage.error('答错了，已放进错题本')
      }
    }

    await progress.fetchProgress()

    if (advanced) {
      kp.value = progress.currentKnowledgePoint
      celebrating.value = true
      question.value = null
      return
    }

    // 稍微停一下让提示看得见，然后自动下一题
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

function leaveToHome() {
  celebrating.value = true // 跳过离开确认
  router.replace('/home')
}

// 有题没做完就离开时要提示；确认后进度已经存在服务端，下次进来会恢复到这一题
onBeforeRouteLeave(async () => {
  if (celebrating.value || !question.value) return true
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
