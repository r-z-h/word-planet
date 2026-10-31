<template>
  <div class="wp-dark page admin-page">
    <StarField />
    <div class="card">
      <div class="head">
        <h2 class="title" style="margin: 0">管理员 · 用户管理</h2>
        <div class="ops">
          <el-button @click="load" :loading="loading">刷新</el-button>
          <el-button text @click="$router.push('/home')">返回首页</el-button>
        </div>
      </div>
      <div class="muted" style="margin: 6px 0 10px">
        共 {{ items.length }} 个账号（最多显示 500）
      </div>

      <el-table :data="items" size="small" style="width: 100%">
        <el-table-column prop="account" label="账号" min-width="120" />
        <el-table-column prop="nickname" label="昵称" min-width="100" />
        <el-table-column prop="level" label="等级" width="80" />
        <el-table-column label="已测" width="70">
          <template #default="{ row }">{{ row.has_tested ? '是' : '否' }}</template>
        </el-table-column>
        <el-table-column label="管理员" width="80">
          <template #default="{ row }">
            <el-tag v-if="row.is_admin" type="warning" size="small" title="该账号拥有管理员权限，可进入管理员后台">管理员</el-tag>
            <span v-else class="wp2-dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="锁定" width="90">
          <template #default="{ row }">
            <el-tag v-if="row.locked_remaining > 0" type="danger" size="small">
              剩 {{ Math.ceil(row.locked_remaining / 60) }} 分
            </el-tag>
            <span v-else class="wp2-dim">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="520">
          <template #default="{ row }">
            <el-button size="small" @click="openReset(row)">重置密码</el-button>
            <el-button size="small" :type="row.is_admin ? 'info' : 'primary'" @click="toggleAdmin(row)">
              {{ row.is_admin ? '取消管理员' : '设为管理员' }}
            </el-button>
            <el-button size="small" type="success" @click="unlockLevel(row)">解锁等级</el-button>
            <el-button size="small" :disabled="row.locked_remaining <= 0" @click="clearLock(row)">解除锁定</el-button>
            <el-button size="small" type="danger" @click="deleteAccount(row)">删除账号</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="resetOpen" class="wp2-dialog" title="重置密码" width="380px">
      <p class="wp2-muted">账号：{{ resetTarget?.account }}</p>
      <el-input v-model="newPassword" type="password" show-password placeholder="新密码（至少 6 位）" />
      <div class="set-foot" style="display: flex; gap: 8px; margin-top: 16px">
        <button class="wp2-btn" style="flex: 1" @click="resetOpen = false">取消</button>
        <button class="wp2-btn gold" style="flex: 1" @click="doReset">确定重置</button>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http, { apiError } from '../api/http'
import StarField from '../components/StarField.vue'

const router = useRouter()
const items = ref([])
const loading = ref(false)
const resetOpen = ref(false)
const resetTarget = ref(null)
const newPassword = ref('')

onMounted(load)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/admin/users')
    items.value = data.items
  } catch (e) {
    if (e?.response?.status === 403) {
      ElMessage.error('需要管理员权限')
      router.replace('/home')
    } else {
      ElMessage.error(apiError(e))
    }
  } finally {
    loading.value = false
  }
}

function openReset(row) {
  resetTarget.value = row
  newPassword.value = ''
  resetOpen.value = true
}

async function doReset() {
  if (!newPassword.value || newPassword.value.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  try {
    await http.post('/admin/reset-password', {
      account: resetTarget.value.account,
      new_password: newPassword.value
    })
    ElMessage.success('密码已重置')
    resetOpen.value = false
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function toggleAdmin(row) {
  const target = !row.is_admin
  try {
    await ElMessageBox.confirm(
      target ? `确定把 ${row.account} 设为管理员？` : `确定取消 ${row.account} 的管理员？`,
      '修改管理员',
      { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    await http.post('/admin/set-admin', { account: row.account, is_admin: target })
    ElMessage.success('已更新')
    await load()
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function unlockLevel(row) {
  try {
    await ElMessageBox.confirm(`把 ${row.account} 解锁到最高等级（L3）？`, '解锁等级', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  try {
    await http.post('/admin/unlock-level', { account: row.account })
    ElMessage.success('已解锁全部等级')
    await load()
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function clearLock(row) {
  try {
    await http.post('/admin/clear-lock', { account: row.account })
    ElMessage.success('已解除锁定')
    await load()
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}

async function deleteAccount(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除账号「${row.account}」？该账号的全部学习数据会被永久删除，不可恢复。`,
      '删除账号',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'error' }
    )
  } catch {
    return
  }
  try {
    await http.post('/admin/delete-account', { account: row.account })
    ElMessage.success('账号已删除')
    await load()
  } catch (e) {
    ElMessage.error(apiError(e))
  }
}
</script>

<style scoped>
.head { display: flex; justify-content: space-between; align-items: center; }
.ops { display: flex; gap: 8px; align-items: center; }
</style>
