import { createRouter, createWebHistory } from 'vue-router'
import { useUserStore } from '../stores/user'

const routes = [
  { path: '/', redirect: '/home' },
  { path: '/login', component: () => import('../views/LoginView.vue') },
  { path: '/register', component: () => import('../views/RegisterView.vue') },
  { path: '/home', component: () => import('../views/HomeView.vue') },
  { path: '/test', component: () => import('../views/TestView.vue') },
  { path: '/play', component: () => import('../views/PlayView.vue') },
  { path: '/modules', redirect: '/home' },
  { path: '/level-test', component: () => import('../views/LevelTestView.vue') },
  { path: '/result', component: () => import('../views/ResultView.vue') },
  { path: '/practice', component: () => import('../views/PracticeView.vue') },
  { path: '/words', component: () => import('../views/WordsView.vue') },
  { path: '/wrong', component: () => import('../views/WrongView.vue') },
  { path: '/achievements', component: () => import('../views/AchievementsView.vue') },
  { path: '/report', component: () => import('../views/ReportView.vue') }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  const user = useUserStore()

  if (to.path === '/login' || to.path === '/register') {
    if (user.token) return { path: '/home' }
    return true
  }

  if (!user.token) return { path: '/login' }

  if (!user.loaded) {
    try {
      await user.fetchMe()
    } catch {
      return { path: '/login' }
    }
  }

  if (!user.hasTested && to.path !== '/test') return { path: '/test' }
  if (user.hasTested && to.path === '/test') return { path: '/home' }

  return true
})

export default router
