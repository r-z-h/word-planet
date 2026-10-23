import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 20000
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('wp_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

http.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status = error?.response?.status
    const code = error?.response?.data?.detail?.code || error?.response?.data?.code
    if (status === 401) {
      localStorage.removeItem('wp_token')
      if (!window.location.hash.includes('/login')) {
        window.location.href = `/login?expired=${code === 'TOKEN_EXPIRED' ? 1 : 0}`
      }
    }
    return Promise.reject(error)
  }
)

export function apiError(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.detail) return detail.detail
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('；')
  return error?.message || '请求失败'
}

export default http
