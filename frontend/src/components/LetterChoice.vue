<template>
  <div>
    <p class="stem">{{ question.stem }}</p>
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
import { computed } from 'vue'

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
</style>
