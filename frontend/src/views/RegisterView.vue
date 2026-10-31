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

    <!-- 点注册后才弹出的人机验证 -->
    <el-dialog v-model="captchaOpen" class="wp2-dialog" title="人机验证" width="360px" :close-on-click-modal="false">
      <p class="cap-tip">为防止批量注册，请先回答：</p>
      <div class="cap-row">
        <span class="cap-q">{{ captchaQuestion }}</span>
        <el-input v-model="captchaCode" placeholder="答案" @keyup.enter="tryAutoSubmit" />
        <el-button text @click="loadCaptcha">换一题</el-button>
      </div>
      <p v-if="captchaError" class="cap-err">{{ captchaError }}</p>
      <div class="cap-foot">
        <button class="wp2-btn" @click="captchaOpen = false">取消</button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
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
const submitting = ref(false)
const agreed = ref(false)
const needCaptcha = ref(true)
const captchaOpen = ref(false)
const captchaQuestion = ref('')
const captchaToken = ref('')
const captchaCode = ref('')
const captchaError = ref('')

onMounted(async () => {
  try {
    const { data } = await http.get('/security-config')
    needCaptcha.value = Boolean(data.require_captcha)
  } catch {
    /* 拿不到就默认需要 */
  }
})

function onSubmit() {
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
  if (!needCaptcha.value) {
    doRegister()
    return
  }
  captchaCode.value = ''
  captchaError.value = ''
  captchaOpen.value = true
  loadCaptcha()
}

async function loadCaptcha() {
  try {
    const { data } = await http.get('/captcha')
    captchaQuestion.value = data.question
    captchaToken.value = data.token
  } catch {
    captchaError.value = '验证码加载失败，请重试'
  }
}

function confirmRegister() {
  tryAutoSubmit()
}

// 答对即自动提交，不用再点按钮
function tryAutoSubmit() {
  if (submitting.value) return
  const m = String(captchaQuestion.value).match(/(\d+)\s*\+\s*(\d+)/)
  if (!m) return
  const expected = Number(m[1]) + Number(m[2])
  const got = Number(String(captchaCode.value).trim())
  if (String(captchaCode.value).trim() === '' || Number.isNaN(got)) return
  if (got === expected) {
    captchaError.value = ''
    doRegister()
  } else if (String(captchaCode.value).trim().length >= String(expected).length) {
    captchaError.value = '答案不对，请再试一次'
  }
}

watch(captchaCode, () => {
  captchaError.value = ''
  tryAutoSubmit()
})

async function doRegister() {
  submitting.value = true
  try {
    await user.register({
      account: account.value.trim(),
      nickname: nickname.value.trim(),
      password: password.value,
      agreed_terms: agreed.value,
      captcha_token: needCaptcha.value ? captchaToken.value : null,
      captcha_code: needCaptcha.value ? captchaCode.value.trim() : null
    })
    captchaOpen.value = false
    router.replace('/test')
  } catch (e) {
    const msg = apiError(e)
    captchaError.value = msg
    ElMessage.error(msg)
    if (needCaptcha.value) loadCaptcha()
  } finally {
    submitting.value = false
    loading.value = false
  }
}
</script>

<style scoped>
.agree { margin: 4px 0 6px; font-size: 12px; color: var(--wp2-muted); }
.cap-tip { color: var(--wp2-muted); font-size: 13px; margin: 0 0 8px; }
.cap-row { display: flex; align-items: center; gap: 8px; }
.cap-q { font-weight: 900; font-size: 16px; color: var(--wp2-gold); min-width: 90px; }
.cap-err { color: #ff9d9d; font-size: 12px; margin: 6px 0 0; }
.cap-foot { display: flex; gap: 8px; margin-top: 16px; }
.cap-foot .wp2-btn { flex: 1; }
</style>
