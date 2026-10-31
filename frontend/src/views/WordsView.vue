<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div class="head">
        <h2 class="title" style="margin: 0">词典</h2>
        <el-button text @click="$router.push('/home')">返回</el-button>
      </div>

      <el-input
        v-model="keyword"
        placeholder="搜英文或中文，只搜当前等级"
        clearable
        style="margin-top: 12px"
        @input="onSearch"
      />
      <div class="muted" style="margin-top: 8px">
        {{ level }} · 共 {{ total }} 个词
        <template v-if="keyword">· 搜索「{{ keyword }}」</template>
      </div>
    </div>

    <div v-loading="loading" class="card">
      <el-empty v-if="!loading && !items.length" description="没有找到这个单词 🌱" />

      <div v-for="item in items" :key="item.id" class="word">
        <div class="word-head">
          <div class="word-title">
            <span class="word-text">{{ item.word }}</span>
            <span v-if="item.phonetic" class="phonetic">{{ item.phonetic }}</span>
            <SpeakButton :text="item.word" />
          </div>
          <el-tag v-if="item.has_wrong" size="small" type="danger">有错题</el-tag>
          <el-tag v-else-if="item.learned" size="small" type="success">已学</el-tag>
          <el-tag v-else size="small" type="info">未学</el-tag>
        </div>

        <div class="senses">
          <div v-for="(sense, index) in visibleSenses(item)" :key="index" class="sense">
            <span class="index">{{ index + 1 }}</span>
            <span>{{ sense.text }}</span>
            <el-tag
              v-if="sense.source === 'textbook'"
              size="small"
              type="warning"
              effect="plain"
              style="margin-left: 6px"
            >
              课本
            </el-tag>
          </div>
        </div>

        <el-button
          v-if="item.senses.length > 2"
          text
          size="small"
          class="expand"
          @click="toggle(item.id)"
        >
          {{ expanded[item.id] ? '收起' : `展开全部 ${item.senses.length} 条义项` }}
        </el-button>

        <div v-if="item.definition_en" class="definition">{{ item.definition_en }}</div>
      </div>

      <div ref="sentinel" class="more">
        <el-button v-if="hasMore" :loading="loadingMore" @click="loadMore">加载更多</el-button>
        <div v-else-if="items.length" class="muted">没有更多了</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import SpeakButton from '../components/SpeakButton.vue'
import StarField from '../components/StarField.vue'

const PAGE_SIZE = 30

const keyword = ref('')
const level = ref('')
const total = ref(0)
const items = ref([])
const offset = ref(0)
const hasMore = ref(false)
const loading = ref(true)
const loadingMore = ref(false)
const expanded = reactive({})
const sentinel = ref(null)

let searchTimer = null
let requestId = 0
let observer = null

function visibleSenses(item) {
  return expanded[item.id] ? item.senses : item.senses.slice(0, 2)
}

function toggle(id) {
  expanded[id] = !expanded[id]
}

async function fetchPage(reset) {
  const rid = ++requestId
  if (reset) {
    offset.value = 0
    items.value = []
    hasMore.value = false
  }
  const params = { offset: offset.value, limit: PAGE_SIZE }
  if (keyword.value.trim()) params.q = keyword.value.trim()
  try {
    if (reset) loading.value = true
    else loadingMore.value = true
    const { data } = await http.get('/words', { params })
    if (rid !== requestId) return
    level.value = data.level
    total.value = data.total
    items.value = reset ? data.items : items.value.concat(data.items)
    offset.value += data.items.length
    hasMore.value = data.has_more
  } catch (e) {
    if (rid === requestId) ElMessage.error(apiError(e))
  } finally {
    if (rid === requestId) {
      loading.value = false
      loadingMore.value = false
    }
  }
}

function onSearch() {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => fetchPage(true), 300)
}

function loadMore() {
  if (!hasMore.value || loadingMore.value || loading.value) return
  fetchPage(false)
}

onMounted(async () => {
  await fetchPage(true)
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) loadMore()
    },
    { rootMargin: '120px' }
  )
  if (sentinel.value) observer.observe(sentinel.value)
})

onBeforeUnmount(() => {
  clearTimeout(searchTimer)
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.word {
  padding: 14px 0;
  border-bottom: 1px solid rgba(255, 232, 180, 0.14);
}
.word:last-of-type {
  border-bottom: none;
}
.word-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.word-title {
  display: flex;
  align-items: baseline;
  gap: 8px;
  min-width: 0;
}
.word-text {
  font-size: 18px;
  font-weight: 900;
  color: var(--wp2-ink);
}
.phonetic {
  color: var(--wp2-muted);
  font-size: 13px;
}
.senses {
  margin-top: 8px;
}
.sense {
  display: flex;
  align-items: baseline;
  gap: 6px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--wp2-muted);
}
.index {
  color: var(--wp2-dim);
  font-size: 12px;
  min-width: 14px;
}
.expand {
  margin-top: 2px;
  padding-left: 0;
}
.definition {
  margin-top: 8px;
  background: rgba(255, 246, 225, 0.06);
  border: 1.5px solid rgba(255, 232, 180, 0.14);
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--wp2-muted);
  white-space: pre-line;
}
.more {
  text-align: center;
  padding-top: 12px;
}
</style>
