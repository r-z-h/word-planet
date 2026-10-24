<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <h2 class="title" style="margin: 0">能力测试</h2>
          <div class="muted">测本级内容，10 题答对 8 题即可通过</div>
        </div>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div v-if="status && !status.can_test" class="card">
      <el-alert
        :title="status.next_level ? '还没达标' : '已经是最高等级'"
        :description="
          status.next_level
            ? `本级每个计入门槛的知识点都要完成 ${status.required_sets} 套，才能开始测试。`
            : '当前是 L3，没有更高等级了。'
        "
        type="warning"
        :closable="false"
      />
      <el-button style="margin-top: 16px" @click="$router.push('/modules')">去学习</el-button>
    </div>

    <div v-else-if="!started" class="card" style="text-align: center; padding: 36px 20px">
      <div style="font-size: 48px">🎯</div>
      <h2 class="title">准备好了吗</h2>
      <p class="muted">
        共 10 题，答对 8 题通过。通过后可以自己决定升到 {{ status?.next_level }} 还是留在本级。
      </p>
      <el-button type="primary" size="large" style="width: 100%; height: 50px" @click="startTest">
        开始测试
      </el-button>
    </div>

    <div v-else-if="question" class="card">
      <div class="muted" style="margin-bottom: 8px">第 {{ index }} / 10 题</div>
      <QuestionRenderer :key="question.id" :question="question" :disabled="submitting" @submit="onAnswer" />
    </div>

    <el-dialog v-model="dialogVisible" title="测试通过" width="360px" :close-on-click-modal="false">
      <p>你答对了 {{ result?.score }} / 10 题，可以进入 {{ result?.next_level }} 了。</p>
      <p class="muted">也可以先留在本级，把基础打牢一点。</p>
      <template #footer>
        <el-button @click="choose(false)">留在本级</el-button>
        <el-button type="primary" @click="choose(true)">进入 {{ result?.next_level }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="failVisible" title="还差一点" width="340px" :close-on-click-modal="false">
      <p>答对了 {{ result?.score }} / 10 题，需要 8 题才能通过。</p>
      <p class="muted">继续在本级练习，随时可以再来测。</p>
      <template #footer>
        <el-button type="primary" @click="$router.push('/modules')">回去练习</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import QuestionRenderer from '../components/QuestionRenderer.vue'

const router = useRouter()

const status = ref(null)
const started = ref(false)
const question = ref(null)
const index = ref(1)
const submitting = ref(false)
const result = ref(null)
const dialogVisible = ref(false)
const failVisible = ref(false)

onMounted(async () => {
  try {
    const { data } = await http.get('/level-test/status')
    status.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  }
})

async function startTest() {
  try {
    const { data } = await http.post('/level-test/start')
    question.value = data.question
    index.value = data.index
    started.value = true
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function onAnswer(answer) {
  if (submitting.value || !question.value) return
  submitting.value = true
  try {
    const { data } = await http.post('/level-test/answer', {
      question_id: question.value.id,
      answer
    })
    if (data.is_finished) {
      result.value = data
      if (data.passed) dialogVisible.value = true
      else failVisible.value = true
      started.value = false
      return
    }
    const next = await http.get('/level-test/next')
    question.value = next.data.question
    index.value = next.data.index
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    submitting.value = false
  }
}

async function choose(goNext) {
  try {
    const { data } = await http.post('/level-test/choose', { go_next: goNext })
    dialogVisible.value = false
    ElMessage.success(goNext ? `已进入 ${data.level}` : '继续留在本级')
    router.replace('/home')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}
</script>
