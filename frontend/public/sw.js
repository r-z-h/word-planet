// 最小 Service Worker：接收推送并展示通知
self.addEventListener('install', (event) => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let payload = { title: 'Word Planet', body: '今天还没开始哦' }
  try {
    if (event.data) payload = event.data.json()
  } catch (e) {
    // 保持默认文案
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Word Planet', {
      body: payload.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png'
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(self.clients.openWindow('/home'))
})
