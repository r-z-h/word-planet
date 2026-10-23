<template>
  <div class="page">
    <div class="card" style="text-align: center; padding: 36px 20px">
      <div class="burst">🎉</div>
      <h2 class="title" style="margin-top: 12px">这个知识点学完啦！</h2>
      <p class="muted" style="margin-bottom: 20px">
        已完成「{{ finishedName || '当前知识点' }}」，继续加油。
      </p>

      <div class="stats">
        <div class="stat">
          <div class="num">{{ completedCount }}</div>
          <div class="muted">累计完成知识点</div>
        </div>
        <div class="stat">
          <div class="num">{{ todayCorrect }}</div>
          <div class="muted">今天答对题数</div>
        </div>
        <div class="stat">
          <div class="num">{{ streakDays }}</div>
          <div class="muted">连续学习天数</div>
        </div>
      </div>

      <el-button
        v-if="nextName"
        type="primary"
        size="large"
        style="width: 100%; margin-top: 24px; height: 50px"
        @click="$router.replace('/play')"
      >
        继续学「{{ nextName }}」
      </el-button>
      <el-button
        v-else
        type="primary"
        size="large"
        style="width: 100%; margin-top: 24px; height: 50px"
        @click="$router.replace('/home')"
      >
        今天的学完了，回首页
      </el-button>
      <el-button text style="margin-top: 10px" @click="$router.replace('/home')">回首页</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import http, { apiError } from '../api/http'
import { ElMessage } from 'element-plus'
import { useProgressStore } from '../stores/progress'

const route = useRoute()
const progress = useProgressStore()

const finishedName = ref(route.query.finished || '')
const streakDays = ref(0)

const completedCount = computed(() => progress.completedKnowledgePoints.length)
const todayCorrect = computed(() => progress.todayTask.correct_count || 0)
const nextName = computed(() => progress.currentKnowledgePoint?.name || '')

onMounted(async () => {
  try {
    await progress.fetchProgress()
    const { data } = await http.get('/streak')
    streakDays.value = data.current_streak
  } catch (e) {
    ElMessage.error(apiError(e))
  }
})
</script>

<style scoped>
.burst {
  font-size: 72px;
  line-height: 1;
  animation: pop 0.7s cubic-bezier(0.2, 1.6, 0.4, 1);
}
@keyframes pop {
  0% {
    transform: scale(0.2);
    opacity: 0;
  }
  60% {
    transform: scale(1.25);
    opacity: 1;
  }
  100% {
    transform: scale(1);
  }
}
.stats {
  display: flex;
  gap: 12px;
  margin-top: 24px;
}
.stat {
  flex: 1;
  background: #f8fafc;
  border-radius: 12px;
  padding: 14px 6px;
}
.num {
  font-size: 24px;
  font-weight: 700;
  color: #4c6ef5;
}
</style>
