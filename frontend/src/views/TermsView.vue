<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div class="head">
        <h2 class="title" style="margin: 0">用户协议</h2>
        <el-button text @click="$router.push('/register')">返回注册</el-button>
      </div>
      <div class="body">
        <p>1. 本应用为英语单词学习工具，注册即表示你同意本协议与《隐私政策》。</p>
        <p>2. 请妥善保管账号密码；账号仅限本人（或监护下的孩子）使用，不得转借、出售。</p>
        <p>3. 学习内容来自公开词表，仅供学习参考；如发现错误可向管理员反馈。</p>
        <p>4. 禁止利用本应用进行任何违法、侵权或干扰服务的行为。</p>
        <p>5. 我们可能因维护、升级暂停服务；对因不可抗力造成的损失不承担责任。</p>
        <p>6. 14 岁以下用户须由监护人同意后使用。</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import StarField from '../components/StarField.vue'
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
.body { color: var(--wp2-muted); font-size: 13.5px; line-height: 1.9; }
</style>
