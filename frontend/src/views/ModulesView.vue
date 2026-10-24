<template>
  <div class="page">
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <h2 class="title" style="margin: 0">选择学习模块</h2>
          <div class="muted">{{ level }} · 每个模块至少完成 {{ requiredSets }} 套</div>
        </div>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div v-loading="loading">
      <div v-for="kp in lesson.knowledgePoints" :key="kp.id" class="card module">
        <div class="row">
          <div>
            <div class="name">
              {{ kp.name }}
              <el-tag v-if="!kp.counts_for_gate" size="small" type="info" style="margin-left: 6px">
                不计门槛
              </el-tag>
            </div>
            <div class="muted">
              已完成 {{ kp.completed_sets }} / {{ kp.total_sets }} 套
              <template v-if="kp.current_set"> · 当前第 {{ kp.current_set }} 套</template>
              <template v-else> · 全部学完</template>
            </div>
          </div>
          <el-button
            type="primary"
            :disabled="kp.current_set === null"
            @click="enter(kp)"
          >
            {{ kp.current_set === null ? '已学完' : '进入' }}
          </el-button>
        </div>
        <el-progress
          :percentage="kp.total_sets ? Math.round((kp.completed_sets / kp.total_sets) * 100) : 0"
          :show-text="false"
          :stroke-width="6"
          style="margin-top: 10px"
        />
        <div v-if="kp.counts_for_gate" class="gate">
          门槛：{{ Math.min(kp.completed_sets, requiredSets) }} / {{ requiredSets }} 套
          <el-tag v-if="kp.meets_gate" size="small" type="success" style="margin-left: 6px">已达成</el-tag>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useLessonStore } from '../stores/lesson'
import { useProgressStore } from '../stores/progress'
import { apiError } from '../api/http'

const router = useRouter()
const lesson = useLessonStore()
const progress = useProgressStore()

const loading = ref(true)
const level = ref('')
const requiredSets = ref(3)

onMounted(async () => {
  try {
    await lesson.fetchOverview()
    level.value = lesson.level
    requiredSets.value = lesson.requiredSets
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
})

async function enter(kp) {
  try {
    await lesson.selectKnowledgePoint(kp.id)
    await progress.fetchProgress()
    router.push('/play')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}
</script>

<style scoped>
.module .row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}
.name {
  font-weight: 700;
  font-size: 16px;
}
.gate {
  margin-top: 8px;
  font-size: 12px;
  color: #64748b;
}
</style>
