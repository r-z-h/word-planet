import { defineStore } from 'pinia'
import http from '../api/http'

export const useUserStore = defineStore('user', {
  state: () => ({
    token: localStorage.getItem('wp_token') || '',
    userId: '',
    nickname: '',
    level: null,
    hasTested: false,
    loaded: false
  }),
  actions: {
    setAuth(payload) {
      this.token = payload.access_token
      localStorage.setItem('wp_token', payload.access_token)
      if (typeof payload.has_tested === 'boolean') this.hasTested = payload.has_tested
      if (payload.level !== undefined) this.level = payload.level
    },
    async login(account, password) {
      const { data } = await http.post('/login', { account, password })
      this.setAuth(data)
      await this.fetchMe()
    },
    async register(payload) {
      const { data } = await http.post('/register', payload)
      this.setAuth(data)
      this.userId = data.user_id
      this.nickname = payload.nickname
      this.hasTested = false
      this.loaded = true
    },
    async fetchMe() {
      const { data } = await http.get('/me')
      this.userId = data.user_id
      this.nickname = data.nickname
      this.level = data.level
      this.hasTested = data.has_tested
      this.loaded = true
      return data
    },
    setLevel(level) {
      this.level = level
      this.hasTested = true
    },
    logout() {
      this.token = ''
      this.userId = ''
      this.nickname = ''
      this.level = null
      this.hasTested = false
      this.loaded = false
      localStorage.removeItem('wp_token')
    }
  }
})
