<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">徽章墙</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div class="card">
      <AchievementWall :items="items" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import AchievementWall from '../components/AchievementWall.vue'

const items = ref([])

onMounted(async () => {
  try {
    const { data } = await http.get('/achievements')
    items.value = data.items
  } catch (e) {
    ElMessage.error(apiError(e))
  }
})
</script>
