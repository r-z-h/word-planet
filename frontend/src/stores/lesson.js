import { defineStore } from 'pinia'
import http from '../api/http'

export const useLessonStore = defineStore('lesson', {
  state: () => ({
    level: null,
    maxLevel: null,
    requiredSets: 3,
    knowledgePoints: [],
    gateReady: false,
    canTest: false,
    nextLevel: null,
    switchableLevels: [],
    loaded: false
  }),
  getters: {
    currentKp(state) {
      return state.knowledgePoints.find((k) => k.current_set !== null) || null
    }
  },
  actions: {
    async fetchOverview() {
      const { data } = await http.get('/lesson/overview')
      this.level = data.level
      this.maxLevel = data.max_level
      this.requiredSets = data.required_sets
      this.knowledgePoints = data.knowledge_points
      this.gateReady = data.gate_ready
      this.canTest = data.can_test
      this.nextLevel = data.next_level
      this.switchableLevels = data.switchable_levels
      this.loaded = true
      return data
    },
    async selectKnowledgePoint(id) {
      const { data } = await http.post('/lesson/select', { knowledge_point_id: id })
      await this.fetchOverview()
      return data
    },
    async switchLevel(level) {
      const { data } = await http.post('/lesson/switch-level', { level })
      await this.fetchOverview()
      return data
    },
    async testStatus() {
      const { data } = await http.get('/level-test/status')
      return data
    }
  }
})
