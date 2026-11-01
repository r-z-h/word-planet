<template>
  <div class="wp-dark page">
    <StarField />

    <div class="card guest-head">
      <div>
        <div class="title" style="font-size: 20px">游客体验</div>
        <div class="muted">无需注册，挑模块随便试几题；注册登录可保存进度、解锁完整内容</div>
      </div>
      <el-button text @click="$router.push('/login')">去登录</el-button>
    </div>

    <!-- 选择模块 -->
    <div v-if="!activeModule && !moduleDone" class="card">
      <div class="sec-title">选一个模块试试</div>
      <div v-if="loadingModules"><el-skeleton :rows="3" animated /></div>
      <div v-else class="mods">
        <button v-for="m in modules" :key="m.id" class="mod" @click="startModule(m)">
          <span class="lv">{{ m.level }}</span>
          <span class="nm">{{ m.name }}</span>
          <span class="cnt">{{ m.question_count }} 题</span>
        </button>
        <div v-if="!modules.length" class="muted">暂无可用模块</div>
      </div>
      <div class="tip muted">跟读模块需要麦克风和在线语音，暂不开放游客体验。</div>
    </div>

    <!-- 做题 -->
    <div v-else-if="activeModule && !moduleDone" class="card">
      <div class="bar">
        <div>
          <div style="font-weight: 700">{{ activeModule.level }} · {{ activeModule.name }}</div>
          <div class="muted">第 {{ idx + 1 }} / {{ questions.length }} 题</div>
        </div>
        <el-button text @click="backToModules">换模块</el-button>
      </div>

      <div v-if="loadingQuestions" style="margin-top: 12px">
        <el-skeleton :rows="4" animated />
      </div>
      <template v-else-if="question">
        <QuestionRenderer
          :key="question.id"
          :question="question"
          :disabled="submitting"
          @submit="onSubmit"
        />

        <div v-if="feedback" style="margin-top: 18px">
          <el-alert
            :title="feedback.is_correct ? '答对了 ✅' : `答错了，正确答案：${feedback.correct_answer}`"
            :type="feedback.is_correct ? 'success' : 'error'"
            :closable="false"
          />

          <div v-if="feedback.word" class="fb-word-box">
            <div class="fb-word">
              <span class="fb-word-text">{{ feedback.word.word }}</span>
              <span v-if="feedback.word.phonetic" class="phonetic">{{ feedback.word.phonetic }}</span>
              <SpeakButton v-if="feedback.word.word" :text="feedback.word.word" />
            </div>
            <div v-if="feedback.word.senses && feedback.word.senses.length" class="senses">
              <div v-for="(sense, i) in feedback.word.senses" :key="i" class="sense">
                <span class="idx">{{ i + 1 }}</span>
                <span>{{ sense.text }}</span>
                <el-tag
                  v-if="sense.source === 'textbook'"
                  size="small"
                  type="warning"
                  effect="plain"
                  style="margin-left: 6px"
                >课本</el-tag>
              </div>
            </div>
            <div v-if="feedback.word.definition_en" class="definition">{{ feedback.word.definition_en }}</div>
          </div>

          <el-button
            type="primary"
            size="large"
            style="width: 100%; margin-top: 16px"
            @click="nextInModule"
          >
            {{ isLast ? '完成本模块' : '下一题' }}
          </el-button>
        </div>
      </template>
      <el-empty v-else description="这个模块暂时没有题" />
    </div>

    <!-- 模块完成 -->
    <div v-else-if="moduleDone" class="card" style="text-align: center; padding: 36px 20px">
      <div style="font-size: 52px">🌟</div>
      <h2 class="title" style="margin: 8px 0">体验完成</h2>
      <p class="muted">{{ activeModule?.level }} · {{ activeModule?.name }} 的 {{ questions.length }} 道题都试完啦</p>
      <p class="muted" style="margin-top: 4px">注册后可以保存进度、记录错题、解锁更多关卡和徽章～</p>
      <div class="done-btns">
        <el-button size="large" @click="backToModules">换一个模块</el-button>
        <el-button type="primary" size="large" @click="$router.push('/register')">注册 / 登录</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import QuestionRenderer from '../components/QuestionRenderer.vue'
import StarField from '../components/StarField.vue'
import SpeakButton from '../components/SpeakButton.vue'

const router = useRouter()

const modules = ref([])
const loadingModules = ref(true)

const activeModule = ref(null)
const questions = ref([])
const idx = ref(0)
const feedback = ref(null)
const submitting = ref(false)
const loadingQuestions = ref(false)
const moduleDone = ref(false)

const question = computed(() => questions.value[idx.value] || null)
const isLast = computed(() => idx.value >= questions.value.length - 1)

onMounted(loadModules)

async function loadModules() {
  loadingModules.value = true
  try {
    const { data } = await http.get('/guest/modules')
    modules.value = data.modules || []
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loadingModules.value = false
  }
}

async function startModule(m) {
  feedback.value = null
  moduleDone.value = false
  loadingQuestions.value = true
  activeModule.value = m
  questions.value = []
  idx.value = 0
  try {
    const { data } = await http.get('/guest/questions', { params: { kp_id: m.id, count: 3 } })
    activeModule.value = data.module || m
    questions.value = data.questions || []
    if (!questions.value.length) ElMessage.warning('这个模块暂时没有题')
  } catch (e) {
    ElMessage.error(apiError(e))
    activeModule.value = null
  } finally {
    loadingQuestions.value = false
  }
}

async function onSubmit(answer) {
  if (submitting.value || !question.value) return
  submitting.value = true
  try {
    const { data } = await http.post('/guest/answer', {
      question_id: question.value.id,
      answer
    })
    feedback.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    submitting.value = false
  }
}

function nextInModule() {
  feedback.value = null
  if (isLast.value) {
    moduleDone.value = true
    return
  }
  idx.value += 1
}

function backToModules() {
  activeModule.value = null
  questions.value = []
  idx.value = 0
  feedback.value = null
  moduleDone.value = false
}
</script>

<style scoped>
.guest-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.sec-title {
  font-weight: 800;
  margin-bottom: 12px;
}
.mods {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}
.mod {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px;
  border-radius: 14px;
  cursor: pointer;
  text-align: left;
  color: inherit;
  background: rgba(255, 255, 255, 0.05);
  border: 1.5px solid rgba(255, 255, 255, 0.12);
}
.mod:hover {
  border-color: rgba(255, 232, 180, 0.5);
}
.mod .lv {
  font-size: 12px;
  font-weight: 800;
  color: #ffd479;
  background: rgba(255, 212, 121, 0.12);
  border-radius: 8px;
  padding: 2px 8px;
}
.mod .nm {
  font-weight: 700;
  flex: 1;
}
.mod .cnt {
  font-size: 12px;
  opacity: 0.7;
}
.bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tip {
  margin-top: 14px;
  font-size: 12.5px;
}
.fb-word-box {
  margin-top: 14px;
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.14);
  border-radius: 12px;
  padding: 14px;
}
.fb-word {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.fb-word-text {
  font-size: 20px;
  font-weight: 800;
}
.phonetic {
  opacity: 0.75;
  font-size: 13px;
}
.senses {
  margin-top: 10px;
}
.sense {
  display: flex;
  gap: 8px;
  line-height: 1.8;
  font-size: 14px;
}
.sense .idx {
  color: #ffd479;
  font-weight: 800;
}
.definition {
  margin-top: 10px;
  opacity: 0.85;
  font-size: 13px;
}
.done-btns {
  margin-top: 18px;
  display: flex;
  gap: 12px;
  justify-content: center;
}
</style>
