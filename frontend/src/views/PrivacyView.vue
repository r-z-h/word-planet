<template>
  <div class="wp-dark page">
    <StarField />
    <div class="card">
      <div class="head">
        <h2 class="title" style="margin: 0">隐私政策</h2>
        <el-button text @click="$router.push('/register')">返回注册</el-button>
      </div>
      <div class="body">
        <p>本应用面向英语单词学习，我们只收集学习必需的信息：</p>
        <ul>
          <li>账号、昵称、密码（密码仅保存不可逆加密值，不保存明文）；</li>
          <li>学习记录：作答、正确率、错题、连续学习天数、奖励（花/星/徽记）；</li>
          <li>跟读录音：仅在你点击麦克风时采集，<b>只在内存中用于本次评分与回放，不保存、不上传留档</b>，关闭页面即消失。</li>
        </ul>
        <p>我们不会出售或向无关第三方提供你的数据。语音评分在启用云服务时，音频会发送至语音服务商用于即时评分，不用于其它用途。</p>
        <p>14 岁以下儿童应在监护人同意与陪同下使用。你可以随时在「设置 → 清空进度」清除学习数据，或「设置 → 注销账号」删除账号及全部数据。</p>
        <p>如需删除数据或有疑问，请联系管理员。</p>
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
.body :deep(ul) { padding-left: 18px; }
.body :deep(b) { color: var(--wp2-ink); }
</style>
