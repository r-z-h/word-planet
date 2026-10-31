<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">徽章墙</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div class="card">
      <div class="title" style="font-size: 15px; margin-bottom: 10px">星球徽记</div>
      <div v-if="!medals.length" class="wp2-dim" style="font-size: 12px">
        还没有徽记。集满 5 颗星可换 1 个徽记，去星球上闯关吧。
      </div>
      <div v-else class="medal-grid">
        <div v-for="m in medals" :key="m.knowledge_point_id" class="medal">
          <div class="em">{{ medalEmoji(m.name) }}</div>
          <div class="nm">{{ m.name }}</div>
          <div class="lv wp2-dim">{{ m.level }} · {{ m.medals }} / {{ m.max_medals }}</div>
          <div class="bar"><i :style="{ width: pct(m) + '%' }" /></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="title" style="font-size: 15px; margin-bottom: 10px">成长徽章</div>
      <AchievementWall :items="items" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import AchievementWall from '../components/AchievementWall.vue'
import StarField from '../components/StarField.vue'

const items = ref([])
const medals = ref([])

const EMOJI = { 基础问候词: '🥚', 常用单词: '🐻', 简单拼写: '✍️', 单词跟读: '🐦', 拼写进阶: '🔮' }

function medalEmoji(name) {
  return EMOJI[name] || '🏅'
}
function pct(m) {
  if (!m.max_medals) return 0
  return Math.min(100, Math.round((m.medals / m.max_medals) * 100))
}

onMounted(async () => {
  try {
    const { data } = await http.get('/achievements')
    items.value = data.items
    medals.value = data.medals || []
  } catch (e) {
    ElMessage.error(apiError(e))
  }
})
</script>

<style scoped>
.medal-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
.medal {
  background: rgba(255, 246, 225, 0.07);
  border: 1.5px solid rgba(255, 232, 180, 0.18);
  border-radius: 14px;
  padding: 12px 10px;
  text-align: center;
}
.medal .em { font-size: 26px; line-height: 1; }
.medal .nm { font-weight: 900; margin-top: 6px; font-size: 13px; color: var(--wp2-ink); }
.medal .lv { font-size: 10.5px; margin-top: 2px; }
.medal .bar {
  height: 6px; border-radius: 99px; margin-top: 8px; overflow: hidden;
  background: rgba(255, 246, 225, 0.12); border: 1.5px solid rgba(255, 232, 180, 0.18);
}
.medal .bar i { display: block; height: 100%; background: linear-gradient(90deg, #ffd166, #f4a340); }
</style>
