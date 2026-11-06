<template>
  <img v-if="isImg" :src="icon" class="medal-img" alt="" />
  <span v-else class="medal-emoji">{{ icon }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  icon: { type: String, default: '' }
})
// 以 / 或 http(s)/data: 开头视为图片地址，否则当 emoji 文本
const isImg = computed(() => /^(\/|https?:|data:)/.test(props.icon || ''))
</script>

<style scoped>
.medal-img {
  width: 1.15em;
  height: 1.15em;
  object-fit: contain;
  vertical-align: -0.18em;
  display: inline-block;
}
</style>
