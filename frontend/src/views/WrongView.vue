<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">错题本</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
      <el-radio-group v-model="scope" style="margin-top: 12px" @change="load">
        <el-radio-button value="all">全部（{{ items.length }}）</el-radio-button>
        <el-radio-button value="current">当前知识点</el-radio-button>
      </el-radio-group>
    </div>

    <div class="card">
      <WrongList :items="items" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import WrongList from '../components/WrongList.vue'

const scope = ref('all')
const items = ref([])

onMounted(load)

async function load() {
  try {
    const { data } = await http.get('/wrong-questions', { params: { scope: scope.value } })
    items.value = data.items
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}
</script>
