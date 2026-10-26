<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <div class="title" style="margin: 0">{{ user.nickname }}</div>
          <div class="muted">
            {{ lesson.level }}<template v-if="lesson.maxLevel && lesson.maxLevel !== lesson.level">
              · 已解锁 {{ lesson.maxLevel }}</template>
          </div>
        </div>
        <el-button text @click="logout">退出</el-button>
      </div>

      <el-divider />

      <StreakBadge :streak="streak" />
    </div>

    <!-- 今天这一套 -->
    <div class="card">
      <div class="muted">今天要学的</div>
      <div class="row" style="margin-top: 6px">
        <div>
          <div style="font-weight: 700; font-size: 17px">
            {{ kp ? kp.name : '还没有可学的模块' }}
          </div>
          <div class="muted" v-if="kp">
            第 {{ progress.set_no || 1 }} 套 · 还剩 {{ progress.todayTask.target_count }} 题
          </div>
        </div>
        <el-button type="primary" :disabled="!kp" @click="goPlay">
          {{ progress.todayTask.is_completed ? '继续学' : '开始学习' }}
        </el-button>
      </div>

      <el-progress
        :percentage="setPercent"
        :show-text="false"
        :stroke-width="8"
        style="margin-top: 12px"
      />
      <div class="muted" style="margin-top: 6px">
        {{ progress.kp_done }} / {{ progress.kp_total }} 题
        <span v-if="kp"> · 该模块已完成 {{ kp.completed_sets }}/{{ kp.total_sets }} 套</span>
      </div>

      <el-button style="margin-top: 12px" @click="$router.push('/modules')">切换学习模块</el-button>
    </div>

    <!-- 能力测试 -->
    <div class="card">
      <div class="row">
        <div>
          <div style="font-weight: 700">能力测试</div>
          <div class="muted">{{ testHint }}</div>
        </div>
        <el-button
          :type="lesson.canTest ? 'success' : 'default'"
          :disabled="!lesson.canTest"
          @click="$router.push('/level-test')"
        >
          {{ lesson.canTest ? '去测试' : '未解锁' }}
        </el-button>
      </div>
    </div>

    <!-- 等级回访 -->
    <div class="card" v-if="lesson.switchableLevels.length > 1">
      <div style="font-weight: 700; margin-bottom: 8px">等级切换</div>
      <div class="muted" style="margin-bottom: 10px">升级后仍可以回到低等级继续练习。</div>
      <el-radio-group v-model="pickedLevel" @change="switchLevel">
        <el-radio-button v-for="lv in lesson.switchableLevels" :key="lv" :value="lv">
          {{ lv }}
        </el-radio-button>
      </el-radio-group>
    </div>

    <div class="card">
      <div class="quick">
        <el-button style="flex: 1" @click="$router.push('/wrong')">📕 错题本</el-button>
        <el-button style="flex: 1" @click="$router.push('/words')">📖 词典</el-button>
        <el-button style="flex: 1" @click="$router.push('/achievements')">🏅 徽章墙</el-button>
        <el-button style="flex: 1" @click="$router.push('/report')">📊 学习报告</el-button>
      </div>
    </div>

    <div class="card">
      <div class="title" style="font-size: 16px">每日提醒</div>
      <p class="muted">开启后，每天晚上 19:00 如果还没学，会收到一次提醒。</p>
      <el-button :disabled="pushState === 'on'" @click="enablePush">
        {{ pushState === 'on' ? '已开启' : '开启提醒' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import { useProgressStore } from '../stores/progress'
import { useLessonStore } from '../stores/lesson'
import StreakBadge from '../components/StreakBadge.vue'

const router = useRouter()
const user = useUserStore()
const progress = useProgressStore()
const lesson = useLessonStore()

const streak = ref({ current_streak: 0, longest_streak: 0, last_study_date: null })
const pushState = ref('off')
const pickedLevel = ref('')

const kp = computed(() => progress.currentKnowledgePoint)
const setPercent = computed(() => {
  if (!progress.kp_total) return 0
  return Math.min(100, Math.round((progress.kp_done / progress.kp_total) * 100))
})
const testHint = computed(() => {
  if (!lesson.nextLevel) return '已经是最高等级'
  if (lesson.canTest) return `本级已达标，可以挑战 ${lesson.nextLevel}`
  return `本级每个计入门槛的模块各完成 ${lesson.requiredSets} 套后可解锁`
})

onMounted(load)

async function load() {
  try {
    await Promise.all([progress.fetchProgress(), lesson.fetchOverview()])
    pickedLevel.value = lesson.level || ''
    const { data } = await http.get('/streak')
    streak.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function goPlay() {
  router.push('/play')
}

async function switchLevel(level) {
  try {
    await lesson.switchLevel(level)
    await progress.fetchProgress()
    user.level = level
    ElMessage.success(`已切换到 ${level}`)
  } catch (e) {
    ElMessage.error(apiError(e))
    pickedLevel.value = lesson.level
  }
}

function logout() {
  user.logout()
  router.replace('/login')
}

async function enablePush() {
  if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
    ElMessage.warning('这个浏览器不支持推送')
    return
  }
  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') {
      ElMessage.warning('没有获得通知权限')
      return
    }
    const reg = await navigator.serviceWorker.register('/sw.js')
    const { data: keyData } = await http.get('/push/public-key')
    if (!keyData.key) {
      ElMessage.warning('服务端还没配置 VAPID 公钥，提醒功能暂不可用')
      return
    }
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(keyData.key)
    })
    await http.post('/push/subscribe', { subscription: sub.toJSON() })
    pushState.value = 'on'
    ElMessage.success('提醒已开启')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}
</script>

<style scoped>
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.quick {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
.quick .el-button {
  flex: 1 1 140px;
  margin-left: 0;
}
</style>
