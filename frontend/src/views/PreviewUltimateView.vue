<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card head-sticky">
      <div style="display: flex; justify-content: space-between; align-items: center">
        <h2 class="title" style="margin: 0">最高成就特效 · 调试预览</h2>
        <el-button text class="back-fixed" @click="$router.push('/home')">返回</el-button>
      </div>
    </div>

    <div class="card">
      <p style="font-size: 13px; color: #a99cc9; line-height: 1.7">
        这个入口可反复进入、反复播放，不是一次性的。<br>
        「完整流程」= 先播 100 秒旅程 CG，结束后中央点亮徽章；「只点亮徽章」用于单独调徽章动画。
      </p>
      <div class="btns">
        <button class="wp2-btn gold" @click="playFull">▶ 播放完整流程（视频+徽章）</button>
        <button class="wp2-btn" @click="playBadge">✦ 只播放徽章点亮</button>
        <button class="wp2-btn" @click="reload">↻ 重置/停止</button>
      </div>
      <p style="font-size: 11px; color: #7f729c; margin-top: 14px">
        提示：播放中可点视频右上角「跳过」直接进入徽章点亮；若按钮无反应，说明上一段还在播放，点「重置/停止」或稍候。
      </p>
    </div>
  </div>
</template>

<script setup>
import StarField from '../components/StarField.vue'
import { playBadgeReveal, playUltimateSequence } from '../utils/ultimateSequence'

function playFull() {
  playUltimateSequence('/videos/ultimate_journey.mp4', '/badges/ultimate.svg')
}
function playBadge() {
  playBadgeReveal('/badges/ultimate.svg')
}
function reload() {
  location.reload()
}
</script>

<style scoped>
.btns { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 6px; }
.btns .wp2-btn { min-width: 210px; }
</style>
