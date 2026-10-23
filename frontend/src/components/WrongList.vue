<template>
  <div>
    <el-empty v-if="!items.length" description="这个范围内还没有错题 🌱" />
    <el-table v-else :data="items" size="small">
      <el-table-column prop="stem" label="题目" show-overflow-tooltip />
      <el-table-column prop="knowledge_point_name" label="知识点" width="110" show-overflow-tooltip />
      <el-table-column prop="error_count" label="错次" width="70" />
    </el-table>
  </div>
</template>

<script setup>
defineProps({
  items: { type: Array, default: () => [] }
})
</script>
