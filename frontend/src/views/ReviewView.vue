<template>
  <div class="wp-dark page">
    <StarField />

    <div class="card" style="display: flex; justify-content: space-between; align-items: center">
      <div>
        <div style="font-weight: 700">再练一次</div>
        <div class="muted">
          {{ info.kp_name || '' }} · 本星球：已做 {{ info.done_sets }} 套 · 未做
          {{ Math.max(info.total_sets - info.done_sets, 0) }} 套 · 共 {{ info.total_sets }} 套
        </div>
      </div>
      <el-button text @click="$router.push('/home')">返回</el-button>
    </div>

    <div v-if="loading" class="card"><el-skeleton :rows="4" animated /></div>

    <div v-else class="card">
      <div style="font-weight: 700; margin-bottom: 10px">选择要重练的套</div>
      <div class="set-grid">
        <el-button size="large" type="primary" @click="go('all')">全部套（{{ info.sets.length }}）</el-button>
        <el-button v-for="s in info.sets" :key="s.set_no" size="large" @click="go(s.set_no)">
          第 {{ s.set_no }} 套（{{ s.total }} 题）
        </el-button>
      </div>
      <div class="muted" style="margin-top: 10px; font-size: 12px">复习与正常做题同一套玩法；只判对错、不推进进度、不计奖励。</div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import StarField from '../components/StarField.vue'

const router = useRouter()
const info = ref({ kp_name: '', total_sets: 0, done_sets: 0, sets: [] })
const loading = ref(true)

onMounted(async () => {
  try {
    const { data } = await http.get('/question/review/sets')
    info.value = {
      kp_name: data.kp_name || '',
      total_sets: data.total_sets || 0,
      done_sets: data.done_sets || 0,
      sets: data.sets || []
    }
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
})

function go(target) {
  router.push({ path: '/play', query: { review: '1', set: target === 'all' ? 'all' : String(target) } })
}
</script>

<style scoped>
.set-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}
</style>
