<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <div class="title" style="margin: 0">{{ user.nickname }}</div>
          <div class="muted">{{ user.level }} · {{ progress.currentKnowledgePoint?.name || '—' }}</div>
        </div>
        <el-button text @click="logout">退出</el-button>
      </div>

      <el-divider />

      <StreakBadge :streak="streak" />

      <div style="margin-top: 16px">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="今天答对">
            {{ progress.todayTask.correct_count }} 题
          </el-descriptions-item>
          <el-descriptions-item label="当前知识点还剩">
            {{ progress.todayTask.target_count }} 题
          </el-descriptions-item>
        </el-descriptions>
        <el-alert
          :title="progress.todayTask.is_completed ? '今天的任务已经完成 ✅' : '学完当前知识点，今天的任务就完成了'"
          :type="progress.todayTask.is_completed ? 'success' : 'info'"
          :closable="false"
          style="margin-top: 12px"
        />
      </div>

      <el-button
        type="primary"
        size="large"
        style="width: 100%; margin-top: 12px; height: 52px; font-size: 17px"
        @click="goPlay"
      >
        继续学习
      </el-button>
    </div>

    <div class="card">
      <div style="display: flex; gap: 10px">
        <el-button style="flex: 1" @click="$router.push('/wrong')">📕 错题本</el-button>
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
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import { useProgressStore } from '../stores/progress'
import StreakBadge from '../components/StreakBadge.vue'

const router = useRouter()
const user = useUserStore()
const progress = useProgressStore()

const streak = ref({ current_streak: 0, longest_streak: 0, last_study_date: null })
const pushState = ref('off')

onMounted(load)

async function load() {
  try {
    await progress.fetchProgress()
    const { data } = await http.get('/streak')
    streak.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function goPlay() {
  router.push('/play')
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
