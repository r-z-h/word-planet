<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card head-sticky">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">徽章墙</h2>
        <el-button text class="back-fixed" @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div class="card">
      <div class="title" style="font-size: 15px; margin-bottom: 10px">成长徽章</div>
      <AchievementWall :items="items" />
    </div>

    <div class="card">
      <div class="title" style="font-size: 15px; margin-bottom: 10px">待解锁成就</div>
      <template v-if="lockedBadges.length">
        <div class="ach-grid">
          <div v-for="b in lockedBadges" :key="b.code" class="abadge locked">
            <span class="lk">🔒</span>
            <div class="ab-ic"><MedalIcon :icon="b.icon || '🏅'" /></div>
            <div class="ab-nm">{{ b.name }}</div>
            <div class="ab-cd">{{ b.condition }}</div>
          </div>
        </div>
      </template>
      <div v-else class="wp2-dim" style="font-size: 12px; margin-bottom: 12px">普通成就已全部解锁 🎉</div>

      <div v-if="ultimate" class="ult-card" :class="{ locked: !ultimate.earned }" @click="onUltimate">
        <div class="ult-ic"><MedalIcon :icon="ultimate.icon || '🏅'" /></div>
        <div class="ult-txt">
          <div class="ult-nm">{{ ultimate.earned ? '' : '🔒 ' }}{{ ultimate.name }}<span class="ult-badge">最高成就</span></div>
          <div class="ult-cd">{{ ultimate.condition }}</div>
        </div>
        <div class="ult-state" :class="{ on: ultimate.earned }">{{ ultimate.earned ? '已解锁 · 点击看特效' : '未解锁' }}</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import AchievementWall from '../components/AchievementWall.vue'
import StarField from '../components/StarField.vue'
import MedalIcon from '../components/MedalIcon.vue'
import { playUltimate } from '../utils/ultimateFx'

const items = ref([])
const badges = ref([])

const ORDER = [
  'streak_3', 'streak_7', 'streak_14', 'active_days_30',
  'answer_100', 'answer_500', 'answer_1000', 'daily_50',
  'complete_l1_first', 'complete_level', 'medals_3_one',
  'perfect_set', 'perfect_10', 'level_test_pass',
  'wrong_cleared', 'refill_10', 'combo_10', 'ultimate_all'
]
const sortedBadges = computed(() =>
  [...badges.value].sort((a, b) => {
    const ia = ORDER.indexOf(a.code)
    const ib = ORDER.indexOf(b.code)
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib)
  })
)
const lockedBadges = computed(() =>
  sortedBadges.value.filter((b) => !b.earned && b.code !== 'ultimate_all')
)
const ultimate = computed(() => badges.value.find((b) => b.code === 'ultimate_all') || null)

function onUltimate() {
  if (ultimate.value?.earned) playUltimate(ultimate.value.icon || '/badges/ultimate.svg')
}

onMounted(async () => {
  try {
    const { data } = await http.get('/achievements')
    items.value = data.items
    badges.value = data.badges || []
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
.all-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 10px;
}
.ach-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.abadge {
  position: relative;
  background: rgba(255, 246, 225, 0.07);
  border: 1.5px solid rgba(255, 232, 180, 0.18);
  border-radius: 14px;
  padding: 14px 8px 10px;
  text-align: center;
  transition: 0.2s;
}
.abadge .lk { position: absolute; top: 8px; right: 10px; font-size: 12px; opacity: 0.8; }
.abadge .ab-ic { height: 46px; display: flex; align-items: center; justify-content: center; font-size: 34px; line-height: 1; }
.abadge .ab-nm { font-weight: 900; font-size: 12.5px; color: var(--wp2-ink); margin-top: 6px; }
.abadge .ab-cd { font-size: 10px; color: var(--wp2-dim); margin-top: 3px; line-height: 1.35; min-height: 26px; }
.abadge.locked { opacity: 0.55; filter: grayscale(1); }
.ult-card {
  display: flex;
  align-items: center;
  gap: 16px;
  background: linear-gradient(180deg, rgba(255, 214, 120, 0.12), rgba(255, 143, 177, 0.06));
  border: 2px solid rgba(255, 214, 120, 0.45);
  border-radius: 16px;
  padding: 16px 18px;
}
.ult-card .ult-ic { font-size: 46px; width: 60px; text-align: center; line-height: 1; }
.ult-card .ult-txt { flex: 1; }
.ult-card .ult-nm { font-size: 16px; font-weight: 900; color: #ffd166; }
.ult-card .ult-badge {
  margin-left: 8px; font-size: 9.5px; padding: 2px 8px; border-radius: 99px;
  background: rgba(255, 214, 120, 0.2); color: #ffd166; border: 1px solid rgba(255, 214, 120, 0.5);
  vertical-align: middle;
}
.ult-card .ult-cd { font-size: 11px; color: #c9b8f0; margin-top: 4px; }
.ult-card .ult-state { font-size: 10px; font-weight: 900; color: #b6a9d6; white-space: nowrap; }
.ult-card .ult-state.on { color: #63e6be; }
.ult-card.locked { opacity: 0.6; filter: grayscale(1); }
</style>
