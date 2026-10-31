<template>
  <div class="wp-dark auth-wrap">
    <StarField />
    <div class="auth-card">
      <h1 class="title" style="text-align: center">创建账号</h1>
      <p class="muted" style="text-align: center; margin-bottom: 20px">
        注册后会先做一个小测试，帮你找到合适的起点
      </p>

      <el-form @submit.prevent="onSubmit">
        <el-form-item>
          <el-input v-model="account" placeholder="账号（3-64 位）" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="nickname" placeholder="昵称" size="large" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="password" type="password" placeholder="密码（至少 6 位）" size="large" show-password />
        </el-form-item>

        <el-form-item v-if="needCaptcha">
          <div class="cap-row">
            <span class="cap-q">{{ captchaQuestion }}</span>
            <el-input v-model="captchaCode" placeholder="答案" style="width: 110px" />
            <el-button text @click="loadCaptcha">换一题</el-button>
          </div>
        </el-form-item>

        <el-checkbox v-model="agreed" class="agree">
          我已阅读并同意
          <el-link type="primary" @click.prevent="$router.push('/terms')">用户协议</el-link>
          与
          <el-link type="primary" @click.prevent="$router.push('/privacy')">隐私政策</el-link>
        </el-checkbox>

        <el-button type="primary" size="large" style="width: 100%; margin-top: 12px" :loading="loading" @click="onSubmit">
          注册并开始
        </el-button>
      </el-form>

      <div style="text-align: center; margin-top: 16px">
        <el-link @click="$router.push('/login')">已有账号，去登录</el-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http, { apiError } from '../api/http'
import { useUserStore } from '../stores/user'
import StarField from '../components/StarField.vue'

const router = useRouter()
const user = useUserStore()

const account = ref('')
const nickname = ref('')
const password = ref('')
const loading = ref(false)
const agreed = ref(false)
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
    /* 忽略：拿不到配置就按不显示验证码 */
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
  if (!account.value.trim() || !nickname.value.trim() || !password.value) {
    ElMessage.warning('请把三项都填上')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  if (!agreed.value) {
    ElMessage.warning('请先阅读并同意用户协议与隐私政策')
    return
  }
  if (needCaptcha.value && !captchaCode.value.trim()) {
    ElMessage.warning('请填写验证码')
    return
  }
  loading.value = true
  try {
    await user.register({
      account: account.value.trim(),
      nickname: nickname.value.trim(),
      password: password.value,
      agreed_terms: agreed.value,
      captcha_token: needCaptcha.value ? captchaToken.value : null,
      captcha_code: needCaptcha.value ? captchaCode.value.trim() : null
    })
    router.replace('/test')
  } catch (e) {
    ElMessage.error(apiError(e))
    if (needCaptcha.value) loadCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cap-row {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.cap-q {
  font-weight: 900;
  font-size: 15px;
  color: var(--wp2-gold);
  min-width: 92px;
}
.agree {
  margin: 4px 0 6px;
  font-size: 12px;
  color: var(--wp2-muted);
}
</style>
