<template>
  <div>
    <p class="stem">{{ question.stem }}</p>
    <el-input
      v-model="value"
      size="large"
      placeholder="在这里拼出英文单词"
      :disabled="disabled"
      clearable
      @keyup.enter="onSubmit"
    />
    <el-button
      type="primary"
      size="large"
      style="width: 100%; margin-top: 16px"
      :loading="disabled"
      @click="onSubmit"
    >
      确认
    </el-button>
    <p class="muted" style="margin-top: 8px">只输入英文字母，不用加标点。</p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage } from 'element-plus'

defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})
const emit = defineEmits(['submit'])

const value = ref('')

function onSubmit() {
  const text = value.value.trim()
  if (!text) {
    ElMessage.warning('先写一个答案吧')
    return
  }
  emit('submit', text)
}
</script>

<style scoped>
.stem {
  font-size: 20px;
  font-weight: 600;
  margin: 4px 0 20px;
  line-height: 1.5;
}
</style>
