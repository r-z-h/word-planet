import { defineStore } from 'pinia'
import http from '../api/http'

export const useProgressStore = defineStore('progress', {
  state: () => ({
    level: null,
    currentKnowledgePoint: null,
    completedKnowledgePoints: [],
    todayTask: { is_completed: false, correct_count: 0, target_count: 0 },
    kpTotal: 0,
    kpDone: 0
  }),
  actions: {
    async fetchProgress() {
      const { data } = await http.get('/progress')
      this.level = data.level
      this.currentKnowledgePoint = data.current_knowledge_point
      this.completedKnowledgePoints = data.completed_knowledge_points || []
      this.todayTask = data.today_task
      this.kpTotal = data.kp_total || 0
      this.kpDone = data.kp_done || 0
      return data
    },
    async submitAnswer(questionId, answer, idempotencyKey) {
      const { data } = await http.post('/answer/submit', {
        question_id: questionId,
        answer,
        idempotency_key: idempotencyKey
      })
      if (data.current_knowledge_point) this.currentKnowledgePoint = data.current_knowledge_point
      return data
    }
  }
})
