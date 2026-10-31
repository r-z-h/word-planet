<template>
  <div class="wp-dark home-page">
    <StarField />

    <div class="home">
      <!-- 顶栏 -->
      <div class="topbar">
        <div class="brand"><span class="orb" />Word Planet <small>单词星球</small></div>
        <div class="pills">
          <span class="pill">🔥 连续 <b>{{ streak }}</b> 天</span>
          <span class="pill">🌸 累计 <b>{{ map.total_flowers }}</b></span>
          <span class="pill gold">⭐ 今日 <b>+{{ map.today_stars }}</b></span>
          <span class="pill">🎯 已解锁 <b>{{ map.max_level || '-' }}</b></span>
        </div>
        <span class="grow" />
        <button class="ibtn" title="设置" @click="settingsOpen = true">设置</button>
      </div>

      <el-dialog v-model="settingsOpen" class="wp2-dialog" title="设置" width="470px" align-center>
        <div class="set-body">
          <div class="set-sec">声音</div>
          <div class="set-row">
            <span>音效</span>
            <el-switch v-model="soundOn" @change="toggleSound" />
          </div>
          <div class="set-row">
            <span>音量</span>
            <el-slider v-model="volume" :min="0" :max="100" :disabled="!soundOn" style="width: 200px" @change="onVolume" />
          </div>

          <div class="set-sec">体验</div>
          <div class="set-row">
            <span>减弱动效 <em class="set-hint">晕动症友好</em></span>
            <el-switch v-model="reduceMotionOn" @change="onMotion" />
          </div>

          <div class="set-sec">提醒</div>
          <div class="set-row">
            <span>每日提醒 <em class="set-hint">推送通知</em></span>
            <el-switch v-model="pushOn" :loading="pushBusy" @change="onPush" />
          </div>

          <div class="set-sec">账号</div>
          <div class="set-row"><span>昵称</span><span class="wp2-muted">{{ user.nickname || '-' }}</span></div>
          <div class="set-row">
            <span>当前等级 / 已解锁</span>
            <span class="wp2-muted">{{ map.level || '-' }} / {{ map.max_level || '-' }}</span>
          </div>
          <div class="set-row">
            <span>修改密码</span>
            <button class="wp2-btn small" @click="pwdOpen = !pwdOpen">{{ pwdOpen ? '收起' : '修改' }}</button>
          </div>
          <div v-if="pwdOpen" class="pwd-box">
            <el-input v-model="pwdOld" type="password" placeholder="原密码" show-password />
            <el-input v-model="pwdNew" type="password" placeholder="新密码（至少 6 位）" show-password />
            <button class="wp2-btn gold small" :disabled="!pwdOld || pwdNew.length < 6" @click="changePwd">
              保存新密码
            </button>
          </div>

          <div class="set-sec">数据</div>
          <div class="set-row">
            <span>清空进度 <em class="set-hint">删作答/错题/徽章/花星徽记，保留账号与等级</em></span>
            <button class="wp2-btn small danger" @click="resetProgress">清空</button>
          </div>
          <div class="set-row">
            <span>清除本机缓存 <em class="set-hint">只清本设备，不动服务器</em></span>
            <button class="wp2-btn small" @click="clearCache">清除</button>
          </div>

          <div class="set-sec">关于</div>
          <div class="set-row"><span>版本</span><span class="wp2-muted">v{{ APP_VERSION }}</span></div>
          <div class="about-line">录音只保存在本机内存、不上传服务器；关闭页面即消失。</div>
        </div>
        <div class="set-foot">
          <button class="wp2-btn" @click="settingsOpen = false">关闭</button>
          <button class="wp2-btn gold" @click="logout">退出登录</button>
        </div>
      </el-dialog>

      <!-- 主体：左地图 + 右栏 -->
      <div class="homebody" v-loading="loading">
        <div class="mapwrap">
          <PlanetMap
            :planets="map.planets"
            :gate-ready="map.gate_ready"
            :next-level="map.next_level"
            :max-level="map.max_level || 'L1'"
            @select="enterPlanet"
            @gate="goGate"
          />

          <!-- 底部 CTA 条 -->
          <div class="cta">
            <div class="txt">
              <div class="t1">第 {{ cur?.current_set || 1 }} 关 · {{ cur?.name || '暂无' }}</div>
              <div class="t2">
                <template v-if="cur">
                  还剩 {{ Math.max(cur.total_sets - cur.completed_sets, 0) }} 套 · 本套 🌸 {{ progress.setFlowers }} · ⭐ {{ progress.setStars }} ·
                  {{ cur.pure ? '纯练' : medalEmoji(cur) + ' ' + progress.setMedals }}
                </template>
                <template v-else>去地图上选一颗星球吧</template>
              </div>
            </div>
            <div class="nums">
              <span class="n"><b>{{ map.today_attempts }}</b><span>今日做题</span></span>
              <span class="sep" />
              <span class="n"><b>{{ accuracy }}</b><span>正确率</span></span>
              <span class="sep" />
              <span class="n"><b>×{{ map.today_max_combo }}</b><span>最高连击</span></span>
              <span class="sep" />
              <span class="n flower"><b>{{ map.today_flowers }}</b><span>今日花</span></span>
              <span class="sep" />
              <span class="n gold"><b>{{ map.today_stars }}</b><span>今日星</span></span>
            </div>
            <div class="week">
              <div class="c">本周节奏</div>
              <div class="bars">
                <div v-for="(n, i) in weekBars" :key="i" class="wd" :class="{ today: i === todayIdx }">
                  <i :style="{ height: barH(n) }" />
                  <span>{{ '一二三四五六日'[i] }}</span>
                </div>
              </div>
            </div>
            <button class="go" :disabled="!cur" @click="continueCurrent">继续闯关 →</button>
          </div>
        </div>

        <!-- 右栏 -->
        <aside class="aside">
          <div class="card">
            <h3>正在闯的星球</h3>
            <div class="kp">
              <span class="dot" :class="cur ? cur.level.toLowerCase() : 'l1'">
                <span class="face" :class="cur && cur.pure ? 'f-proud' : 'f-excited'"><i class="e1" /><i class="e2" /><b /></span>
              </span>
              <div>
                <div class="nm">{{ cur?.name || '暂无' }}</div>
                <div class="sub">{{ cur?.level }} · {{ typeName(cur) }} · 第 {{ cur?.current_set || 1 }} / {{ cur?.total_sets || 0 }} 套</div>
              </div>
            </div>
            <div class="bar"><i :style="{ width: curPct + '%' }" /></div>
            <div class="barlab"><span>{{ cur?.completed_sets || 0 }} 套已完成</span><span>{{ cur?.total_sets || 0 }} 套</span></div>

            <div class="chain3">
              <span class="layer">🌸 {{ progress.setFlowers }}<em>朵</em></span>
              <span class="ar">→</span>
              <span class="layer">⭐ {{ progress.setStars }}<em>颗</em></span>
              <span class="ar">→</span>
              <span class="layer hot">{{ cur ? medalEmoji(cur) : '🏅' }} {{ progress.setMedals }}<em>个</em></span>
            </div>

            <div class="btnrow">
              <button class="ebtn" :disabled="progress.exchangeableStars < 1" @click="exchange('flower')">
                🌸3 → ⭐1
              </button>
              <button class="ebtn" :disabled="!progress.canExchangeMedal" @click="exchange('star')">
                ⭐5 → 徽记
              </button>
            </div>
          </div>

          <div class="card">
            <h3>解锁路线</h3>
            <div class="steps">
              <div class="step">
                <span class="lv">L1</span>
                <span class="need">字母表完成 + 3 个 🥚</span>
                <span :class="steps.l1ok ? 'ok' : 'no'">{{ steps.l1Text }}</span>
              </div>
              <div class="down">↓ 能力测试 10 题 · 对 8 过</div>
              <div class="step">
                <span class="lv">L2</span>
                <span class="need">🐻3 + ✍️2 + 🐦2</span>
                <span :class="steps.l2ok ? 'ok' : 'no'">{{ steps.l2Text }}</span>
              </div>
              <div class="down">↓ 能力测试 10 题 · 对 8 过</div>
              <div class="step">
                <span class="lv">L3</span>
                <span class="need">{{ steps.l3Need }}</span>
                <span :class="steps.l3ok ? 'ok' : 'no'">{{ steps.l3Text }}</span>
              </div>
            </div>
          </div>

          <div class="card">
            <h3>快捷入口</h3>
            <div class="quick">
              <button @click="router.push('/wrong')">📕 错题本 {{ wrongItems.length }}</button>
              <button @click="router.push('/words')">📖 词典</button>
              <button @click="router.push('/achievements')">🏅 徽章墙</button>
              <button @click="router.push('/report')">📊 报告</button>
            </div>
          </div>

          <div class="card">
            <h3>待补花错题 <span v-if="wrongItems.length" class="cnt">{{ wrongItems.length }}</span></h3>
            <div class="wrongs">
              <div v-for="w in wrongItems.slice(0, 2)" :key="w.question_id" class="wrong">
                <span class="q">{{ w.stem }}</span>
                <span class="e">错 {{ w.error_count }} 次</span>
              </div>
              <div v-if="!wrongItems.length" class="wrong empty">暂时没有错题，真棒！</div>
            </div>
            <div class="hintline">补完这些错题，这套才能拿到徽记</div>
            <button class="ebtn wide" @click="router.push('/wrong')">📕 去错题本补花</button>
          </div>

          <div class="card">
            <h3>下一个目标</h3>
            <div class="goal">
              <span class="goal-icon">{{ goal.icon }}</span>
              <span class="goal-text" v-html="goal.text" />
            </div>
            <button class="ebtn wide" @click="goalGo">{{ goal.btn }}</button>
          </div>
        </aside>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import { useProgressStore } from '../stores/progress'
import { useLessonStore } from '../stores/lesson'
import StarField from '../components/StarField.vue'
import PlanetMap from '../components/game/PlanetMap.vue'
import { isSoundOn, setSoundOn } from '../utils/sfx'
import { getVolume, setVolume, isMotionReduced, setMotionReduced, clearLocalCache } from '../utils/prefs'

const APP_VERSION = '1.4.0'
const router = useRouter()
const user = useUserStore()
const progress = useProgressStore()
const lesson = useLessonStore()

const loading = ref(true)
const streak = ref(0)
const settingsOpen = ref(false)
const soundOn = ref(isSoundOn())
const volume = ref(Math.round(getVolume() * 100))
const reduceMotionOn = ref(isMotionReduced())
const pushOn = ref(
  typeof Notification !== 'undefined' &&
    Notification.permission === 'granted' &&
    localStorage.getItem('wp_push') === '1'
)
const pushBusy = ref(false)
const pwdOpen = ref(false)
const pwdOld = ref('')
const pwdNew = ref('')
const wrongItems = ref([])
const map = ref({
  planets: [],
  today_flowers: 0,
  today_stars: 0,
  total_flowers: 0,
  today_attempts: 0,
  today_correct: 0,
  today_max_combo: 0,
  week_counts: [],
  gate_ready: false,
  next_level: null,
  level: null,
  max_level: null
})

const MEDAL = { 基础问候词: '🥚', 常用单词: '🐻', 简单拼写: '✍️', 单词跟读: '🐦', 拼写进阶: '🔮' }
const TYPE = { letter: '字母选择题', word: '单词选择题', spelling: '拼写题', listening: '听力题', pronunciation: '跟读题' }

const cur = computed(() => map.value.planets.find((p) => p.is_current && !p.locked) || null)
const curPct = computed(() => {
  const c = cur.value
  if (!c || !c.total_sets) return 0
  return Math.round((c.completed_sets / c.total_sets) * 100)
})
const accuracy = computed(() => {
  const a = map.value.today_attempts
  if (!a) return '—'
  return Math.round((map.value.today_correct / a) * 100) + '%'
})
const todayIdx = computed(() => (new Date().getDay() + 6) % 7)
const weekBars = computed(() => {
  const w = map.value.week_counts || []
  return Array.from({ length: 7 }, (_, i) => w[i] || 0)
})
function barH(n) {
  const max = Math.max(1, ...weekBars.value)
  return Math.round(4 + (n / max) * 22) + 'px'
}
function medalEmoji(p) {
  return MEDAL[p?.name] || '🏅'
}
function typeName(p) {
  return TYPE[p?.question_type] || ''
}

const steps = computed(() => {
  const by = (n) => map.value.planets.find((p) => p.name === n)
  const letter = by('字母表')
  const greet = by('基础问候词')
  const bear = by('常用单词')
  const spell = by('简单拼写')
  const pron = by('单词跟读')

  const l1done = (letter?.is_complete ? 1 : 0) + Math.min(greet?.medals || 0, 3)
  const l1ok = !!letter?.is_complete && (greet?.medals || 0) >= 3
  const l2have = Math.min(bear?.medals || 0, 3) + Math.min(spell?.medals || 0, 2) + Math.min(pron?.medals || 0, 2)
  const l2ok = (bear?.medals || 0) >= 3 && (spell?.medals || 0) >= 2 && (pron?.medals || 0) >= 2
  const l3ok = (map.value.max_level || 'L1') >= 'L3'
  return {
    l1ok,
    l1Text: `${Math.min(l1done, 4)}/4 ${l1ok ? '✓' : ''}`.trim(),
    l2ok,
    l2Text: `${l2have} / 7`,
    l3ok,
    l3Need: l3ok ? '已解锁' : '🔒 需先通过 L2 能力测试',
    l3Text: l3ok ? '✓' : '未解锁'
  }
})

const goal = computed(() => {
  const by = (n) => map.value.planets.find((p) => p.name === n)
  if ((map.value.max_level || 'L1') === 'L3') {
    return { icon: '🏆', text: '已经是最高等级，继续收集徽记吧', btn: '去常用单词', name: '常用单词' }
  }
  if ((map.value.max_level || 'L1') === 'L1') {
    const need = Math.max(0, 3 - (by('基础问候词')?.medals || 0))
    return {
      icon: '🥚',
      text: `再拿 <b>${need} 个</b> 🥚 就能挑战 L2`,
      btn: '去基础问候词',
      name: '基础问候词'
    }
  }
  const need = Math.max(0, 3 - (by('常用单词')?.medals || 0))
  return {
    icon: '🐻',
    text: `再拿 <b>${need} 个</b> 🐻 就能挑战 L3`,
    btn: '去常用单词',
    name: '常用单词'
  }
})

onMounted(load)

async function load() {
  loading.value = true
  try {
    const [{ data: m }, { data: s }, wrongResp] = await Promise.all([
      http.get('/lesson/map'),
      http.get('/streak'),
      http.get('/wrong-questions').catch(() => ({ data: { items: [] } }))
    ])
    map.value = m
    streak.value = s.current_streak
    wrongItems.value = (wrongResp.data.items || []).filter((x) => !x.is_mastered)
    await Promise.all([progress.fetchProgress(), lesson.fetchOverview()])
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}

async function enterPlanet(planet) {
  if (planet.locked) return
  try {
    if (planet.level !== map.value.level) {
      await http.post('/lesson/switch-level', { level: planet.level })
    }
    await http.post('/lesson/select', { knowledge_point_id: planet.id })
    await progress.fetchProgress()
    router.push('/play')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function continueCurrent() {
  if (cur.value) router.push('/play')
}

function goGate() {
  if (map.value.gate_ready && map.value.next_level) router.push('/level-test')
  else ElMessage.info('本级还没达标，先把各星球练到门槛')
}

async function exchange(fromKind) {
  if (!cur.value) return
  try {
    const key = window.crypto?.randomUUID
      ? window.crypto.randomUUID().replace(/-/g, '')
      : `${Date.now()}${Math.random().toString(16).slice(2)}`
    const { data } = await http.post('/reward/exchange', {
      knowledge_point_id: cur.value.id,
      set_no: cur.value.current_set || 1,
      from_kind: fromKind,
      amount: 1,
      idempotency_key: key
    })
    await Promise.all([progress.fetchProgress(), load()])
    ElMessage.success(fromKind === 'flower' ? '兑换成功：🌸3 → ⭐1' : '兑换成功：⭐5 → 徽记')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

function goalGo() {
  const p = map.value.planets.find((x) => x.name === goal.value.name)
  if (p) enterPlanet(p)
}

function toggleSound(v) {
  setSoundOn(v)
}

function onVolume(v) {
  setVolume(v)
}

function onMotion(v) {
  setMotionReduced(v)
}

async function onPush(v) {
  pushBusy.value = true
  try {
    if (v) {
      if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        throw new Error('这个浏览器不支持推送')
      }
      const perm = await Notification.requestPermission()
      if (perm !== 'granted') {
        pushOn.value = false
        ElMessage.warning('没有获得通知权限')
        return
      }
      const reg = await navigator.serviceWorker.register('/sw.js')
      const { data: keyData } = await http.get('/push/public-key')
      if (!keyData.key) {
        pushOn.value = false
        ElMessage.warning('服务端还没配置推送公钥，提醒暂不可用')
        return
      }
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(keyData.key)
      })
      await http.post('/push/subscribe', { subscription: sub.toJSON() })
      localStorage.setItem('wp_push', '1')
      ElMessage.success('已开启每日提醒')
    } else {
      const reg = await navigator.serviceWorker.getRegistration()
      const sub = reg && (await reg.pushManager.getSubscription())
      if (sub) await sub.unsubscribe()
      await http.delete('/push/unsubscribe')
      localStorage.removeItem('wp_push')
      ElMessage.success('已关闭提醒')
    }
  } catch (e) {
    pushOn.value = !v
    ElMessage.error(apiError(e))
  } finally {
    pushBusy.value = false
  }
}

async function changePwd() {
  try {
    await http.post('/change-password', { old_password: pwdOld.value, new_password: pwdNew.value })
    pwdOld.value = ''
    pwdNew.value = ''
    pwdOpen.value = false
    ElMessage.success('密码已修改')
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function resetProgress() {
  try {
    await ElMessageBox.confirm(
      '将删除你的全部作答记录、错题、徽章、花/星/徽记与套进度（账号和等级保留）。此操作不可恢复，确定吗？',
      '清空学习进度',
      { confirmButtonText: '确定清空', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await http.post('/reset-progress')
    ElMessage.success('学习进度已清空')
    settingsOpen.value = false
    setTimeout(() => window.location.reload(), 400)
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function clearCache() {
  try {
    await ElMessageBox.confirm('清除本机缓存（不动服务器进度），之后会重新加载页面。', '清除本机缓存', {
      confirmButtonText: '清除',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  clearLocalCache()
  window.location.reload()
}

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

function logout() {
  settingsOpen.value = false
  user.logout()
  router.replace('/login')
}
</script>

<style scoped>
.home-page { min-height: 100vh; padding: 12px; box-sizing: border-box; }
.home {
  position: relative;
  z-index: 1;
  max-width: 1440px;
  margin: 0 auto;
  height: calc(100vh - 24px);
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: radial-gradient(120% 90% at 30% 0%, #38205f, #170e33 70%);
  border-radius: 24px;
  border: 2px solid rgba(255, 226, 168, 0.18);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  overflow: hidden;
}

.topbar {
  flex: none; display: flex; align-items: center; gap: 11px; padding: 13px 20px;
  border-bottom: 2px solid rgba(255, 226, 168, 0.14);
}
.brand { display: flex; align-items: center; gap: 9px; font-weight: 900; font-size: 16.5px; color: var(--wp2-ink); }
.brand .orb {
  width: 26px; height: 26px; border-radius: 50%;
  background: radial-gradient(circle at 32% 28%, #c0a8ff, #845ef7 70%);
  border: 2.5px solid var(--wp2-inkline); box-shadow: 0 3px 0 var(--wp2-inkline);
}
.brand small { font-weight: 700; color: var(--wp2-muted); font-size: 10px; letter-spacing: 0.16em; }
.pills { display: flex; gap: 7px; margin-left: 8px; flex-wrap: wrap; }
.pill {
  display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; border-radius: 999px;
  background: rgba(255, 246, 225, 0.11); border: 2px solid rgba(255, 232, 180, 0.36);
  font-size: 11.5px; color: var(--wp2-muted); font-weight: 700;
}
.pill b { color: var(--wp2-ink); font-size: 12.5px; font-weight: 900; }
.pill.gold { background: rgba(255, 205, 76, 0.16); border-color: rgba(255, 205, 76, 0.6); color: #ffe1a0; }
.pill.gold b { color: var(--wp2-gold); }
.grow { flex: 1; }
.ibtn {
  min-width: 36px; height: 36px; padding: 0 10px; border-radius: 11px; cursor: pointer;
  background: rgba(255, 246, 225, 0.1); color: var(--wp2-ink); font-size: 12px; font-weight: 800;
  border: 2px solid rgba(255, 232, 180, 0.36); display: grid; place-items: center;
}
.ibtn.lv.on { background: rgba(255, 205, 76, 0.2); color: var(--wp2-gold); border-color: rgba(255, 205, 76, 0.6); }

.homebody { flex: 1; min-height: 0; display: flex; gap: 12px; padding: 10px 12px; overflow: hidden; }
.mapwrap { flex: 1; min-width: 0; min-height: 0; display: flex; flex-direction: column; gap: 8px; }

/* 底部 CTA 条 */
.cta {
  flex: none; margin: 0 2px; display: flex; align-items: center; gap: 12px;
  padding: 8px 12px; border-radius: 14px; background: var(--wp2-panel);
  border: 2px solid rgba(255, 226, 168, 0.2); box-shadow: 0 8px 22px rgba(0, 0, 0, 0.34);
}
.cta .txt { flex: none; min-width: 180px; }
.cta .t1 { font-size: 13.5px; font-weight: 900; color: var(--wp2-ink); }
.cta .t2 { font-size: 11px; color: var(--wp2-muted); margin-top: 2px; font-weight: 700; }
.cta .nums { display: flex; align-items: center; gap: 11px; }
.cta .n { text-align: center; }
.cta .n b { display: block; font-size: 15.5px; font-weight: 900; line-height: 1.15; color: var(--wp2-ink); }
.cta .n span { font-size: 9.5px; color: var(--wp2-muted); font-weight: 700; }
.cta .n.gold b { color: var(--wp2-gold); }
.cta .n.flower b { color: #ff9db4; }
.cta .sep { width: 1px; height: 22px; background: rgba(255, 232, 180, 0.2); }
.cta .week { flex: 1; min-width: 110px; }
.cta .week .c { font-size: 9px; color: var(--wp2-dim); font-weight: 800; letter-spacing: 0.1em; margin-bottom: 4px; }
.cta .bars { display: flex; align-items: flex-end; gap: 5px; height: 26px; }
.cta .wd { display: flex; flex-direction: column; align-items: center; justify-content: flex-end; gap: 3px; flex: 1; }
.cta .wd i {
  display: block; width: 100%; max-width: 13px; border-radius: 3px 3px 2px 2px;
  background: linear-gradient(180deg, rgba(201, 184, 240, 0.72), rgba(201, 184, 240, 0.38));
}
.cta .wd.today i { background: linear-gradient(180deg, #ffd166, #f4a340); box-shadow: 0 0 10px rgba(255, 205, 76, 0.5); }
.cta .wd span { font-size: 8.5px; color: var(--wp2-muted); font-weight: 800; }
.cta .wd.today span { color: var(--wp2-gold); }
.go {
  flex: none; border-radius: 13px; padding: 11px 20px; cursor: pointer;
  background: linear-gradient(180deg, #ffd166, #f4a340); color: #3a2109;
  font-size: 13.5px; font-weight: 900; border: 3px solid var(--wp2-inkline); box-shadow: 0 5px 0 var(--wp2-inkline);
}
.go[disabled] { filter: grayscale(1) brightness(0.75); cursor: default; }

/* 右栏 */
.aside { flex: none; width: 300px; display: flex; flex-direction: column; gap: 7px; overflow-y: auto; }
.card { background: var(--wp2-panel); border: 2px solid rgba(255, 226, 168, 0.18); border-radius: 14px; padding: 10px 11px 9px; }
.card h3 { font-size: 9.5px; letter-spacing: 0.15em; color: var(--wp2-muted); font-weight: 800; margin: 0 0 7px; display: flex; align-items: center; }
.cnt {
  display: inline-grid; place-items: center; min-width: 16px; height: 16px; padding: 0 4px;
  margin-left: 4px; border-radius: 99px; font-size: 9.5px; font-weight: 900; background: #ff5a5a; color: #fff;
}
.kp { display: flex; align-items: center; gap: 10px; }
.kp .dot {
  width: 40px; height: 40px; border-radius: 50%; flex: none; overflow: hidden;
  border: 2.5px solid var(--wp2-inkline); box-shadow: 0 3px 0 var(--wp2-inkline);
  display: grid; place-items: center;
}
.kp .dot.l1 { background: radial-gradient(circle at 32% 28%, var(--wp2-l1b), var(--wp2-l1) 72%); }
.kp .dot.l2 { background: radial-gradient(circle at 32% 28%, var(--wp2-l2b), var(--wp2-l2) 72%); }
.kp .dot.l3 { background: radial-gradient(circle at 32% 28%, var(--wp2-l3b), var(--wp2-l3) 72%); }
.kp .dot .face { position: relative; width: 40px; height: 40px; }
.kp .dot .face i { position: absolute; background: var(--wp2-inkline); }
.kp .dot .face .e1 { left: 9px; top: 11px; width: 5px; height: 7px; border-radius: 50%; }
.kp .dot .face .e2 { right: 9px; top: 11px; width: 5px; height: 7px; border-radius: 50%; }
.kp .dot .face b { position: absolute; left: 50%; transform: translateX(-50%); top: 22px; width: 11px; height: 7px; background: var(--wp2-inkline); border-radius: 3px 3px 7px 7px; }
.kp .nm { font-size: 14px; font-weight: 900; color: var(--wp2-ink); }
.kp .sub { font-size: 10.5px; color: var(--wp2-muted); margin-top: 2px; }
.bar { height: 7px; border-radius: 99px; background: rgba(255, 246, 225, 0.12); margin-top: 10px; overflow: hidden; border: 2px solid rgba(255, 232, 180, 0.18); }
.bar i { display: block; height: 100%; background: linear-gradient(90deg, #6ff0c4, #12b886); transition: width 0.4s; }
.barlab { display: flex; justify-content: space-between; font-size: 10px; color: var(--wp2-muted); margin-top: 5px; font-weight: 700; }

.chain3 { display: flex; align-items: center; gap: 4px; margin-top: 10px; }
.layer {
  display: flex; align-items: center; gap: 4px; padding: 4px 9px; border-radius: 999px;
  background: rgba(255, 246, 225, 0.08); border: 1.5px solid rgba(255, 232, 180, 0.24);
  font-size: 11.5px; font-weight: 900; color: var(--wp2-ink); white-space: nowrap;
}
.layer em { font-style: normal; font-size: 9.5px; color: var(--wp2-muted); font-weight: 700; }
.layer.hot { background: rgba(255, 205, 76, 0.14); border-color: rgba(255, 205, 76, 0.5); }
.ar { color: var(--wp2-dim); font-size: 10px; font-weight: 900; }

.btnrow { display: flex; gap: 6px; margin-top: 9px; }
.ebtn {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 4px;
  padding: 7px 6px; border-radius: 9px; cursor: pointer; font-size: 10.5px; font-weight: 900;
  background: linear-gradient(180deg, #ffd166, #f4a340); color: #3a2109;
  border: 2px solid var(--wp2-inkline); box-shadow: 0 3px 0 var(--wp2-inkline);
}
.ebtn[disabled] { filter: grayscale(1) brightness(0.72); cursor: default; box-shadow: none; }
.ebtn.wide { width: 100%; margin-top: 8px; }

.steps { display: flex; flex-direction: column; gap: 7px; }
.step { display: flex; align-items: center; gap: 7px; font-size: 10.5px; color: var(--wp2-muted); font-weight: 700; }
.step .lv { width: 20px; font-weight: 900; color: var(--wp2-ink); font-size: 10.5px; }
.step .need { flex: 1; line-height: 1.5; }
.step .ok { color: #6ff0c4; font-weight: 900; font-size: 10px; }
.step .no { color: var(--wp2-dim); font-weight: 800; font-size: 10px; }
.down { text-align: center; color: var(--wp2-dim); font-size: 9.5px; }

.quick { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
.quick button {
  display: flex; align-items: center; gap: 6px; padding: 8px 9px; cursor: pointer;
  background: rgba(255, 246, 225, 0.07); border: 2px solid rgba(255, 232, 180, 0.18);
  border-radius: 10px; color: var(--wp2-ink); font-size: 11px; font-weight: 800; text-align: left;
}

.wrongs { display: flex; flex-direction: column; gap: 5px; }
.wrong {
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
  padding: 6px 8px; border-radius: 9px; background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.16);
}
.wrong .q { font-size: 10.5px; color: var(--wp2-ink); font-weight: 700; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.wrong .e { font-size: 9px; color: #ff9db4; font-weight: 800; flex: none; }
.wrong.empty { color: var(--wp2-dim); font-size: 10.5px; justify-content: center; }
.hintline { font-size: 9.5px; color: var(--wp2-dim); margin: 7px 0 8px; line-height: 1.5; }

.goal { display: flex; align-items: center; gap: 8px; }
.goal-icon { font-size: 20px; line-height: 1; flex: none; }
.goal-text { font-size: 10.5px; color: var(--wp2-muted); font-weight: 700; line-height: 1.6; }
.goal-text :deep(b) { color: var(--wp2-ink); font-weight: 900; }

.set-row {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  padding: 9px 2px; font-size: 13px; font-weight: 700; color: var(--wp2-ink);
  border-bottom: 1px solid rgba(255, 226, 168, 0.12);
}
.set-body { max-height: 60vh; overflow-y: auto; padding-right: 2px; }
.set-sec {
  margin: 12px 0 2px; font-size: 9.5px; letter-spacing: 0.16em;
  color: var(--wp2-dim); font-weight: 900;
}
.set-sec:first-child { margin-top: 2px; }
.set-hint { font-style: normal; font-size: 10px; color: var(--wp2-dim); margin-left: 4px; font-weight: 700; }
.pwd-box { display: flex; flex-direction: column; gap: 8px; padding: 10px 2px 12px; }
.pwd-box .wp2-btn { align-self: flex-end; }
.about-line { font-size: 10.5px; color: var(--wp2-dim); line-height: 1.6; padding: 6px 2px 2px; }
.wp2-btn.small { padding: 6px 12px; font-size: 11.5px; box-shadow: 0 3px 0 var(--wp2-inkline); }
.wp2-btn.danger { background: rgba(255, 90, 90, 0.18); color: #ffb3b3; border-color: rgba(255, 90, 90, 0.55); }
.set-foot { display: flex; gap: 8px; margin-top: 16px; }
.set-foot .wp2-btn { flex: 1; }

@media (max-width: 1023px) {
  .home { height: auto; min-height: calc(100vh - 24px); overflow: visible; }
  .homebody { flex-direction: column; overflow: visible; }
  .aside { width: 100%; overflow: visible; }
  .cta { flex-wrap: wrap; }
  .cta .week { display: none; }
}
@media (max-width: 767px) {
  .home-page { padding: 6px; }
  .home { border-radius: 16px; }
  .topbar { padding: 8px 10px; gap: 6px; flex-wrap: nowrap; align-items: center; }
  .brand { font-size: 13.5px; white-space: nowrap; flex: none; }
  .brand small { display: none; }
  .brand .orb { width: 22px; height: 22px; }
  .pills { display: none; }
  .grow { flex: 1; }
  .ibtn { min-width: 32px; height: 30px; font-size: 11px; padding: 0 8px; white-space: nowrap; }
  .cta .txt { min-width: 0; }
  .cta .nums { gap: 8px; flex-wrap: wrap; }
  .cta .n b { font-size: 13px; }
}
</style>
