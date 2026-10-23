<template>
  <div>
    <div style="text-align: center; margin: 8px 0 20px">
      <el-button type="primary" size="large" circle :disabled="disabled" @click="play">
        <span style="font-size: 24px">🔊</span>
      </el-button>
      <p class="muted" style="margin-top: 8px">点一下听句子，再选出你听到的那个词</p>
    </div>

    <el-button
      v-for="key in keys"
      :key="key"
      class="big-option"
      :disabled="disabled"
      @click="$emit('submit', key)"
    >
      <b style="margin-right: 10px">{{ key }}</b>{{ question.options?.[key] }}
    </el-button>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
defineEmits(['submit'])

const keys = computed(() => Object.keys(props.question.options || {}).sort())

function play() {
  if (!('speechSynthesis' in window)) return
  window.speechSynthesis.cancel()
  const utter = new SpeechSynthesisUtterance(props.question.stem)
  utter.lang = 'en-US'
  utter.rate = 0.9
  window.speechSynthesis.speak(utter)
}

onMounted(() => {
  setTimeout(play, 300)
})
</script>
