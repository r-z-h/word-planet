<template>
  <div class="wp-dark auth-wrap">
    <StarField />
    <div class="auth-card">
      <h1 class="title" style="text-align: center">Word Planet</h1>
      <p class="muted" style="text-align: center; margin-bottom: 20px">每天一点点，单词星球慢慢长大</p>

      <el-alert v-if="expired" title="登录已过期，请重新登录" type="warning" :closable="false" style="margin-bottom: 16px" />

      <el-form @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="account" placeholder="账号" size="large" autocomplete="username" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="password"
            type="password"
            placeholder="密码"
            size="large"
            show-password
            autocomplete="current-password"
            @keyup.enter="onSubmit"
          />
        </el-form-item>

        <el-form-item v-if="needCaptcha">
          <div class="cap-row">
            <span class="cap-q">{{ captchaQuestion }}</span>
            <el-input v-model="captchaCode" placeholder="答案" style="width: 110px" />
            <el-button text @click="loadCaptcha">换一题</el-button>
          </div>
        </el-form-item>

        <el-button type="primary" size="large" style="width: 100%" :loading="loading" @click="onSubmit">
          登录
        </el-button>
      </el-form>

      <div style="text-align: center; margin-top: 16px">
        <el-link type="primary" @click="$router.push('/register')">还没有账号？去注册</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import StarField from '../components/StarField.vue'

const router = useRouter()
const route = useRoute()
const user = useUserStore()

const account = ref('')
const password = ref('')
const loading = ref(false)
const expired = ref(route.query.expired === '1')
const needCaptcha = ref(false)
const captchaQuestion = ref('')
const captchaToken = ref('')
const captchaCode = ref('')

onMounted(async () => {
  try {
    const { data } = await http.get('/security-config')
    needCaptcha.value = Boolean(data.require_captcha)
    if (needCaptcha.value) await loadCaptcha()
  } catch {
    /* ignore */
  }
})

async function loadCaptcha() {
  try {
    const { data } = await http.get('/captcha')
    captchaQuestion.value = data.question
    captchaToken.value = data.token
    captchaCode.value = ''
  } catch {
    /* ignore */
  }
}

async function onSubmit() {
  if (!account.value || !password.value) {
    ElMessage.warning('请填写账号和密码')
    return
  }
  if (needCaptcha.value && !captchaCode.value.trim()) {
    ElMessage.warning('请填写验证码')
    return
  }
  loading.value = true
  try {
    await http.post('/login', {
      account: account.value.trim(),
      password: password.value,
      captcha_token: needCaptcha.value ? captchaToken.value : null,
      captcha_code: needCaptcha.value ? captchaCode.value.trim() : null
    }).then(({ data }) => user.setAuth(data))
    await user.fetchMe()
    router.replace(user.hasTested ? '/home' : '/test')
  } catch (e) {
    ElMessage.error(apiError(e))
    if (needCaptcha.value) loadCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cap-row { display: flex; align-items: center; gap: 8px; width: 100%; }
.cap-q { font-weight: 900; font-size: 15px; color: var(--wp2-gold); min-width: 92px; }
</style>
