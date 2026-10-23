<template>
  <el-button
    :size="size"
    :circle="circle"
    text
    class="speak-btn"
    :title="`朗读：${text}`"
    @click.stop="speak"
  >
    <span :style="{ fontSize: fontSize }">🔊</span>
  </el-button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  text: { type: String, required: true },
  lang: { type: String, default: 'en-US' },
  size: { type: String, default: 'small' },
  circle: { type: Boolean, default: false },
  rate: { type: Number, default: 0.9 }
})

const fontSize = computed(() => (props.size === 'large' ? '22px' : '16px'))

function speak() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utterance = new SpeechSynthesisUtterance(props.text)
  utterance.lang = props.lang
  utterance.rate = props.rate
  window.speechSynthesis.speak(utterance)
}
</script>

<style scoped>
.speak-btn {
  padding: 4px 6px;
}
</style>
