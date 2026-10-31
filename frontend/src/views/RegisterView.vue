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
          <el-input
            v-model="password"
            type="password"
            placeholder="密码（至少 6 位）"
            size="large"
            show-password
          />
        </el-form-item>
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="onSubmit"
        >
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
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import { apiError } from '../api/http'
import StarField from '../components/StarField.vue'

const router = useRouter()
const user = useUserStore()

const account = ref('')
const nickname = ref('')
const password = ref('')
const loading = ref(false)

async function onSubmit() {
  if (!account.value.trim() || !nickname.value.trim() || !password.value) {
    ElMessage.warning('请把三项都填上')
    return
  }
  if (password.value.length < 6) {
    ElMessage.warning('密码至少 6 位')
    return
  }
  loading.value = true
  try {
    await user.register({
      account: account.value.trim(),
      nickname: nickname.value.trim(),
      password: password.value
    })
    router.replace('/test')
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}
</script>
