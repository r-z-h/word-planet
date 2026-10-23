<template>
  <component
    :is="current"
    v-if="current"
    :question="question"
    :disabled="disabled"
    @submit="$emit('submit', $event)"
  />
  <el-alert v-else :title="`未知题型：${question?.question_type}`" type="error" :closable="false" />
</template>

<script setup>
import { computed } from 'vue'
import LetterChoice from './LetterChoice.vue'
import WordChoice from './WordChoice.vue'
import SpellingGame from './SpellingGame.vue'
import ListeningChoice from './ListeningChoice.vue'
import PronunciationGame from './PronunciationGame.vue'

const props = defineProps({
  question: { type: Object, required: true },
  disabled: { type: Boolean, default: false }
})

defineEmits(['submit'])

const map = {
  letter: LetterChoice,
  word: WordChoice,
  spelling: SpellingGame,
  listening: ListeningChoice,
  pronunciation: PronunciationGame
}

const current = computed(() => map[props.question?.question_type])
</script>
