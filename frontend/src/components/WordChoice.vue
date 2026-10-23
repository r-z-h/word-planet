<template>
  <div>
    <p class="stem">{{ question.stem }}</p>
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
import { computed } from 'vue'
import SpeakButton from './SpeakButton.vue'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
defineEmits(['submit'])

const keys = computed(() => Object.keys(props.question.options || {}).sort())
</script>

<style scoped>
.stem {
  font-size: 20px;
  font-weight: 600;
  margin: 4px 0 20px;
  line-height: 1.5;
}
.opt-row {
  display: flex;
  align-items: center;
  gap: 6px;
}
.opt-row .big-option {
  flex: 1;
}
</style>
