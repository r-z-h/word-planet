<template>
  <div class="wp-dark auth-wrap">
    <StarField />
    <div class="auth-card">
      <h1 class="title" style="text-align: center">Word Planet</h1>
      <p class="muted" style="text-align: center; margin-bottom: 20px">
        每天一点点，单词星球慢慢长大
      </p>

      <el-alert
        v-if="expired"
        title="登录已过期，请重新登录"
        type="warning"
        :closable="false"
        style="margin-bottom: 16px"
      />

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
        <el-button
          type="primary"
          size="large"
          style="width: 100%"
          :loading="loading"
          @click="onSubmit"
        >
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
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useUserStore } from '../stores/user'
import { apiError } from '../api/http'
import StarField from '../components/StarField.vue'

const router = useRouter()
const route = useRoute()
const user = useUserStore()

const account = ref('')
const password = ref('')
const loading = ref(false)
const expired = ref(route.query.expired === '1')

async function onSubmit() {
  if (!account.value || !password.value) {
    ElMessage.warning('请填写账号和密码')
    return
  }
  loading.value = true
  try {
    await user.login(account.value.trim(), password.value)
    router.replace(user.hasTested ? '/home' : '/test')
  } catch (e) {
    ElMessage.error(apiError(e))
  } finally {
    loading.value = false
  }
}
</script>
