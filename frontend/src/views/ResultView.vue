<template>
  <div class="wp-dark result-page">
    <StarField />
    <div v-loading="loading" class="rp-inner">
      <div class="rp-card">
        <!-- 纯练星球 -->
        <template v-if="isPure">
          <h2 class="rp-title">{{ title }}</h2>
          <div class="rp-pure-icon">{{ planet?.is_complete ? '✓' : '…' }}</div>
          <p class="rp-meta">{{ pureText }}</p>
        </template>

        <!-- 产奖励星球 -->
        <template v-else>
          <h2 class="rp-title">{{ title }}</h2>
          <div class="rp-sub">{{ stars5Text }}</div>

          <div class="rp-three">
            <div class="rp-col">
              <div class="rp-lab">小红花</div>
              <div class="rp-val">🌸 {{ summary.flowers }}</div>
              <div class="rp-cap">
                {{ summary.flowers >= 15 ? '满 15 朵' : `差 ${15 - summary.flowers} 朵` }}
              </div>
            </div>
            <div class="rp-arrow">→</div>
            <div class="rp-col">
              <div class="rp-lab">星星</div>
              <div class="rp-val">⭐ {{ summary.stars }}</div>
              <div class="rp-cap">
                {{ summary.stars >= 5 ? '满 5 颗' : `差 ${5 - summary.stars} 颗` }}
              </div>
            </div>
            <div class="rp-arrow">→</div>
            <div class="rp-col" :class="{ off: summary.medals === 0 }">
              <div class="rp-lab">徽记</div>
              <div class="rp-val">{{ summary.medals }}</div>
              <div class="rp-cap">{{ summary.medals > 0 ? '本套产出' : '还没拿到' }}</div>
            </div>
          </div>

          <div class="rp-btns">
            <button
              class="wp2-btn"
              :disabled="summary.exchangeable_stars < 1"
              @click="exchange('flower')"
            >
              🌸3 → ⭐1{{ summary.exchangeable_stars < 1 ? '（花不够）' : '' }}
            </button>
            <button
              class="wp2-btn"
              :disabled="!summary.can_exchange_medal"
              @click="exchange('star')"
            >
              ⭐5 → 徽记{{ summary.can_exchange_medal ? '' : '（星不够）' }}
            </button>
          </div>
        </template>

        <div class="rp-foot">
          <button class="wp2-btn" @click="router.replace('/home')">回地图</button>
          <button class="wp2-btn gold" @click="again">再来一次</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useProgressStore } from '../stores/progress'
import StarField from '../components/StarField.vue'

const route = useRoute()
const router = useRouter()
const progress = useProgressStore()

const loading = ref(true)
const finishedName = ref(route.query.kp || '')
const setNo = ref(Number(route.query.set) || 0)
const planet = ref(null)
const summary = ref({
  flowers: 0,
  stars: 0,
  medals: 0,
  exchangeable_stars: 0,
  can_exchange_medal: false,
  planet_medals: 0
})

const isPure = computed(() => !!(planet.value && planet.value.pure))
const title = computed(() =>
  isPure.value
    ? `第 ${setNo.value} 关 · ${finishedName.value}`
    : `第 ${setNo.value} 关完成 · ${finishedName.value}`
)

const stars5Text = computed(() => {
  const n = Math.min(5, Math.floor(summary.value.stars))
  return '★'.repeat(n) + '☆'.repeat(5 - n)
})

const pureText = computed(() => {
  if (!planet.value) return ''
  return planet.value.is_complete ? '✓ 已完成（15 题全对）' : '还有题目没答对，回去继续吧'
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    const { data: map } = await http.get('/lesson/map')
    planet.value = map.planets.find((p) => p.name === finishedName.value) || null
    if (planet.value && !planet.value.pure) {
      const { data } = await http.get('/reward/summary', {
        params: { knowledge_point_id: planet.value.id, set_no: setNo.value || 1 }
      })
      summary.value = data
    }
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}

function newKey() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '')
  return `${Date.now()}${Math.random().toString(16).slice(2)}`
}

async function exchange(fromKind) {
  if (!planet.value) return
  try {
    const { data } = await http.post('/reward/exchange', {
      knowledge_point_id: planet.value.id,
      set_no: setNo.value || 1,
      from_kind: fromKind,
      amount: 1,
      idempotency_key: newKey()
    })
    summary.value = data.summary
    await progress.fetchProgress()
    ElMessage.success(fromKind === 'flower' ? '兑换成功：🌸3 → ⭐1' : '兑换成功：⭐5 → 徽记')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function again() {
  router.replace('/play')
}
</script>

<style scoped>
.result-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
  box-sizing: border-box;
}
.rp-inner { position: relative; z-index: 1; width: 100%; max-width: 560px; }
.rp-card {
  background: var(--wp2-panel);
  border: 2px solid rgba(255, 226, 168, 0.22);
  border-radius: 20px;
  padding: 22px;
  text-align: center;
}
.rp-title { font-size: 20px; font-weight: 900; color: var(--wp2-ink); }
.rp-sub { font-size: 22px; color: var(--wp2-gold); letter-spacing: 4px; margin-top: 6px; }
.rp-three { display: flex; align-items: stretch; gap: 7px; margin: 16px 0 6px; }
.rp-col {
  flex: 1; text-align: center; padding: 12px 6px; border-radius: 13px;
  background: rgba(255, 246, 225, 0.055); border: 2px solid rgba(255, 232, 180, 0.15);
}
.rp-col.off { opacity: 0.45; }
.rp-lab { font-size: 9.5px; letter-spacing: 0.12em; color: var(--wp2-dim); font-weight: 800; }
.rp-val { font-size: 20px; font-weight: 900; color: var(--wp2-gold); margin-top: 5px; }
.rp-cap { font-size: 9.5px; color: var(--wp2-muted); margin-top: 3px; font-weight: 700; }
.rp-arrow { display: grid; place-items: center; color: var(--wp2-dim); font-weight: 900; }
.rp-btns { display: flex; gap: 8px; margin-top: 12px; }
.rp-btns .wp2-btn { flex: 1; }
.rp-foot { display: flex; gap: 8px; margin-top: 14px; }
.rp-foot .wp2-btn { flex: 1; }
.rp-pure-icon { font-size: 54px; color: var(--wp2-l2b); font-weight: 900; margin: 10px 0; }
.rp-meta { font-size: 13px; color: var(--wp2-muted); }
@media (max-width: 767px) {
  .rp-card { padding: 16px; }
  .rp-val { font-size: 17px; }
}
</style>
