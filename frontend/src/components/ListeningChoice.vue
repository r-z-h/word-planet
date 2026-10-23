<template>
  <div>
    <div style="text-align: center; margin: 8px 0 20px">
      <el-button type="primary" size="large" circle :disabled="disabled" @click="play">
        <span style="font-size: 24px">🔊</span>
      </el-button>
      <p class="muted" style="margin-top: 8px">点一下听句子，再选出你听到的那个词</p>
    </div>

    <div v-for="key in keys" :key="key" class="opt-row">
      <el-button
        class="big-option"
        :disabled="disabled"
        @click="$emit('submit', key)"
      >
        <b style="margin-right: 10px">{{ key }}</b>{{ question.options?.[key] }}
      </el-button>
      <SpeakButton :text="String(question.options?.[key] || '')" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import SpeakButton from './SpeakButton.vue'
import { speak } from '../utils/speech'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
defineEmits(['submit'])

const keys = computed(() => Object.keys(props.question.options || {}).sort())

function play() {
  speak(props.question.stem, { rate: 0.9 })
}

onMounted(() => {
  setTimeout(play, 300)
})
</script>

<style scoped>
.opt-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.opt-row .big-option {
  flex: 1;
}
</style>
