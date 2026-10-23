<template>
  <el-button
    :size="size"
    :circle="circle"
    text
    class="speak-btn"
    :title="`朗读：${text}`"
    @click.stop="speakNow"
  >
    <span :style="{ fontSize: fontSize }">🔊</span>
  </el-button>
</template>

<script setup>
import { computed } from 'vue'
import { speak } from '../utils/speech'

const props = defineProps({
  text: { type: String, required: true },
  lang: { type: String, default: 'en-US' },
  size: { type: String, default: 'small' },
  circle: { type: Boolean, default: false },
  rate: { type: Number, default: 0.9 }
})

const fontSize = computed(() => (props.size === 'large' ? '22px' : '16px'))

function speakNow() {
  speak(props.text, { lang: props.lang, rate: props.rate })
}
</script>

<style scoped>
.speak-btn {
  padding: 4px 6px;
}
</style>
