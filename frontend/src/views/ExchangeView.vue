<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card head-sticky">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <div>
          <h2 class="title" style="margin: 0">兑换 · {{ planet?.name || '' }}</h2>
          <div class="muted">
            {{ planet?.level }} · 星球徽记 <MedalIcon :icon="planet?.medal_icon || '🏅'" /> {{ planet?.medal_name || '' }} {{ planet?.medals || 0 }} / {{ planet?.max_medals || 0 }} · 共 {{ planet?.total_sets || 0 }} 套
          </div>
        </div>
        <el-button text class="back-fixed" @click="$router.push('/home')">返回</el-button>
      </div>
      <p class="tip">花 = 答对/补花获得；3 花→1 星，5 星→1 星球徽记。不足的按钮会置灰。本页只显示当前星球，切换星球请回首页地图。</p>
    </div>

    <div v-loading="loading" class="card">
      <template v-if="done.length">
        <h3 class="sec">已完成（{{ done.length }}）</h3>
        <div v-for="s in done" :key="'d' + s.set_no" class="row">
          <span class="sn">第 {{ s.set_no }} 套</span>
          <span class="meta">🌸{{ s.flowers }}/{{ s.total_count }} · ⭐{{ s.stars }} · 徽记{{ s.medals_granted }}</span>
          <button class="mini" :disabled="busy === s.set_no || s.exchangeable_stars < 1" @click="doExchange(s.set_no, 'flower')">🌸3→⭐1</button>
          <button class="mini" :disabled="busy === s.set_no || !s.can_exchange_medal" @click="doExchange(s.set_no, 'star')">⭐5→徽记</button>
        </div>
      </template>

      <template v-if="doing.length">
        <h3 class="sec">进行中</h3>
        <div v-for="s in doing" :key="'i' + s.set_no" class="row">
          <span class="sn">第 {{ s.set_no }} 套</span>
          <span class="meta">🌸{{ s.flowers }}/{{ s.total_count }} · ⭐{{ s.stars }} · 徽记{{ s.medals_granted }}</span>
          <button class="mini" :disabled="busy === s.set_no || s.exchangeable_stars < 1" @click="doExchange(s.set_no, 'flower')">🌸3→⭐1</button>
          <button class="mini" :disabled="busy === s.set_no || !s.can_exchange_medal" @click="doExchange(s.set_no, 'star')">⭐5→徽记</button>
        </div>
      </template>

      <template v-if="todo.length">
        <h3 class="sec" style="cursor: pointer" @click="showTodo = !showTodo">
          未开始（{{ todo.length }}）{{ showTodo ? '▾' : '▸' }}
        </h3>
        <template v-if="showTodo">
          <div v-for="s in todo" :key="'n' + s.set_no" class="row muted">
            <span class="sn">第 {{ s.set_no }} 套</span>
            <span class="meta">未开始 · 🌸0/{{ s.total_count }}</span>
          </div>
        </template>
      </template>

      <el-empty
        v-if="!loading && !done.length && !doing.length && !todo.length"
        description="这个星球还没有题目 / 暂无套"
      />
    </div>

    <div v-loading="historyLoading" class="card">
      <h3 class="sec">兑换记录</h3>
      <div class="sum-grid">
        <div class="sum"><div class="sv">⭐×{{ history.total_stars }}</div><div class="sl">累计兑换星星</div></div>
        <div class="sum"><div class="sv"><MedalIcon :icon="planet?.medal_icon || '🏅'" /> ×{{ planet?.medals ?? history.total_medals }}</div><div class="sl">星球徽记 · {{ planet?.medal_name || '' }}</div></div>
        <div class="sum"><div class="sv">🌸×{{ history.flowers_spent }}</div><div class="sl">消耗花朵</div></div>
        <div class="sum"><div class="sv">×{{ history.exchange_count }}</div><div class="sl">兑换次数</div></div>
      </div>
      <div v-if="history.items && history.items.length" class="hist">
        <div v-for="(h, i) in history.items" :key="i" class="hrow">
          <span class="ht">{{ fmtTime(h.created_at) }}</span>
          <span class="hs">第 {{ h.set_no ?? '—' }} 套</span>
          <span class="hk">{{ h.to_kind === 'star' ? '🌸3 → ⭐1' : '⭐5 → 徽记' }} ×{{ h.amount }}</span>
        </div>
      </div>
      <div v-else class="muted" style="font-size: 12px">还没有兑换记录。答对攒花后可在这里兑换。</div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import StarField from '../components/StarField.vue'
import MedalIcon from '../components/MedalIcon.vue'

const router = useRouter()
const loading = ref(true)
const planet = ref(null)
const sets = ref([])
const busy = ref(null)
const showTodo = ref(false)
const history = ref({ total_stars: 0, total_medals: 0, flowers_spent: 0, exchange_count: 0, items: [] })
const historyLoading = ref(true)

const done = computed(() => sets.value.filter((s) => s.status === 'completed'))
const doing = computed(() => sets.value.filter((s) => s.status === 'in_progress'))
const todo = computed(() => sets.value.filter((s) => s.status === 'not_started'))

onMounted(load)

function newKey() {
  return window.crypto?.randomUUID
    ? window.crypto.randomUUID().replace(/-/g, '')
    : `${Date.now()}${Math.random().toString(16).slice(2)}`
}

async function load() {
  loading.value = true
  try {
    const { data: map } = await http.get('/lesson/map')
    planet.value =
      map.planets.find((p) => p.is_current && !p.locked) ||
      map.planets.find((p) => p.is_current) ||
      null
    if (planet.value) {
      const { data } = await http.get('/lesson/planet-sets', {
        params: { knowledge_point_id: planet.value.id }
      })
      sets.value = data.sets || []
      await loadHistory()
    }
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  if (!planet.value) return
  historyLoading.value = true
  try {
    const { data } = await http.get('/reward/exchange-history', {
      params: { knowledge_point_id: planet.value.id }
    })
    history.value = data
  } catch {
    /* 记录加载失败不阻塞主流程 */
  } finally {
    historyLoading.value = false
  }
}

function fmtTime(value) {
  if (!value) return ''
  const d = new Date(value)
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

async function doExchange(setNo, fromKind) {
  if (!planet.value || busy.value) return
  busy.value = setNo
  try {
    await http.post('/reward/exchange', {
      knowledge_point_id: planet.value.id,
      set_no: setNo,
      from_kind: fromKind,
      amount: 1,
      idempotency_key: newKey()
    })
    await load()
    ElMessage.success(fromKind === 'flower' ? '兑换成功：🌸3 → ⭐1' : '兑换成功：⭐5 → 徽记')
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    busy.value = null
  }
}
</script>

<style scoped>
.tip {
  font-size: 11px;
  color: var(--wp2-dim);
  line-height: 1.6;
  margin-top: 10px;
}
.sec {
  font-size: 12px;
  font-weight: 900;
  color: var(--wp2-gold);
  margin: 14px 0 8px;
}
.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 10px;
  margin-bottom: 6px;
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.16);
  flex-wrap: wrap;
}
.row.muted {
  opacity: 0.6;
}
.sn {
  width: 60px;
  flex: none;
  font-weight: 900;
  font-size: 12px;
  color: var(--wp2-ink);
}
.meta {
  flex: 1;
  font-size: 11px;
  color: var(--wp2-muted);
  font-weight: 700;
}
.mini {
  padding: 5px 9px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 900;
  color: #3a2109;
  background: linear-gradient(180deg, #ffd166, #f4a340);
  border: 2px solid var(--wp2-inkline);
  box-shadow: 0 2px 0 var(--wp2-inkline);
  cursor: pointer;
}
.mini[disabled] {
  filter: grayscale(1) brightness(0.75);
  cursor: default;
}
.sum-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}
.sum {
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.16);
  border-radius: 12px;
  padding: 10px 8px;
  text-align: center;
}
.sum .sv { font-size: 18px; font-weight: 900; color: var(--wp2-gold); }
.sum .sl { font-size: 10.5px; color: var(--wp2-dim); margin-top: 3px; }
.hist { display: flex; flex-direction: column; gap: 6px; }
.hrow {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 7px 10px;
  border-radius: 9px;
  background: rgba(255, 246, 225, 0.05);
  border: 1.5px solid rgba(255, 232, 180, 0.14);
  font-size: 11px;
}
.hrow .ht { color: var(--wp2-dim); width: 118px; flex: none; }
.hrow .hs { color: var(--wp2-ink); font-weight: 800; width: 70px; flex: none; }
.hrow .hk { color: var(--wp2-muted); font-weight: 700; flex: 1; }
@media (max-width: 640px) {
  .sum-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
