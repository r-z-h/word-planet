<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">错题本</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>

      <div class="summary">
        <div class="box">
          <div class="num">{{ summary.pending }}</div>
          <div class="muted">待练习</div>
        </div>
        <div class="box">
          <div class="num">{{ summary.mastered }}</div>
          <div class="muted">已掌握</div>
        </div>
      </div>

      <el-button
        type="primary"
        size="large"
        style="width: 100%; margin-top: 14px; height: 48px"
        :disabled="!summary.pending"
        @click="startPractice"
      >
        {{ summary.pending ? '开始练习错题' : '暂时没有要练的错题' }}
      </el-button>

      <el-select
        v-model="selectedKp"
        placeholder="全部知识点"
        clearable
        style="width: 100%; margin-top: 12px"
        @change="loadList"
      >
        <el-option label="全部知识点" value="" />
        <el-option
          v-for="item in summary.by_knowledge_point"
          :key="item.knowledge_point_id"
          :label="`${item.level} ${item.knowledge_point_name}（${item.pending}）`"
          :value="item.knowledge_point_id"
        />
      </el-select>
    </div>

    <div class="card">
      <el-empty v-if="!items.length" description="这个范围内还没有错题 🌱" />
      <div v-else>
        <div v-for="item in items" :key="item.question_id" class="row">
          <div class="row-head">
            <span class="stem">{{ item.stem }}</span>
            <SpeakButton :text="item.stem" />
          </div>
          <div class="row-meta">
            <el-tag size="small" type="info">{{ item.knowledge_point_name }}</el-tag>
            <span class="muted">错 {{ item.error_count }} 次</span>
            <el-tag v-if="item.is_mastered" size="small" type="success">已掌握</el-tag>
          </div>
          <div v-if="item.explanation" class="explain">{{ item.explanation }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import SpeakButton from '../components/SpeakButton.vue'
import StarField from '../components/StarField.vue'

const router = useRouter()

const items = ref([])
const summary = ref({ pending: 0, mastered: 0, by_knowledge_point: [] })
const selectedKp = ref('')

onMounted(async () => {
  await loadSummary()
  await loadList()
})

async function loadSummary() {
  try {
    const { data } = await http.get('/practice/summary')
    summary.value = data
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function loadList() {
  try {
    const params = { scope: 'all' }
    if (selectedKp.value) params.knowledge_point_id = selectedKp.value
    const { data } = await http.get('/wrong-questions', { params })
    items.value = data.items
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function startPractice() {
  router.push({ path: '/practice', query: selectedKp.value ? { kp: selectedKp.value } : {} })
}
</script>

<style scoped>
.summary {
  display: flex;
  gap: 12px;
  margin-top: 14px;
}
.box {
  flex: 1;
  background: rgba(255, 246, 225, 0.07);
  border: 1.5px solid rgba(255, 232, 180, 0.18);
  border-radius: 12px;
  padding: 12px;
  text-align: center;
}
.num {
  font-size: 22px;
  font-weight: 900;
  color: var(--wp2-gold);
}
.row {
  padding: 14px 0;
  border-bottom: 1px solid rgba(255, 232, 180, 0.14);
}
.row:last-child {
  border-bottom: none;
}
.row-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.stem {
  font-weight: 600;
  line-height: 1.5;
  color: var(--wp2-ink);
}
.row-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 6px;
}
.explain {
  margin-top: 8px;
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.14);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--wp2-muted);
}
</style>
