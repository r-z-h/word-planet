<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">学习报告</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div v-if="report" class="card">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="当前等级">{{ report.level }}</el-descriptions-item>
        <el-descriptions-item label="已完成知识点">
          {{ report.completed_knowledge_points }} / {{ report.total_knowledge_points }}
        </el-descriptions-item>
        <el-descriptions-item label="近 7 天学完知识点">
          {{ report.last_7_days_completed }} 天
        </el-descriptions-item>
        <el-descriptions-item label="近 7 天答题">
          {{ totalAttempts }} 次
        </el-descriptions-item>
      </el-descriptions>
    </div>

    <div v-if="report" class="card">
      <div class="title" style="font-size: 16px">每天答题量</div>
      <ReportCharts :daily="report.daily_attempts" />
    </div>

    <div v-if="report" class="card">
      <div class="title" style="font-size: 16px">错题情况</div>
      <el-empty v-if="!report.wrong_questions.length" description="还没有错题" />
      <el-table v-else :data="report.wrong_questions" size="small">
        <el-table-column prop="stem" label="题目" show-overflow-tooltip />
        <el-table-column prop="error_count" label="错次" width="70" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_mastered ? 'success' : 'warning'" size="small">
              {{ row.is_mastered ? '已掌握' : '待复习' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import ReportCharts from '../components/ReportCharts.vue'
import StarField from '../components/StarField.vue'

const report = ref(null)

const totalAttempts = computed(() =>
  report.value ? report.value.daily_attempts.reduce((sum, d) => sum + d.count, 0) : 0
)

onMounted(async () => {
  try {
    const { data } = await http.get('/report')
    report.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  }
})
</script>
