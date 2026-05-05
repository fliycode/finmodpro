<script setup>
import { useRouter } from 'vue-router';
const router = useRouter();
</script>

<template>
  <div class="admin-not-found">
    <strong>404</strong>
    <p>页面不存在</p>
    <el-button size="small" @click="router.push('/admin/overview')">返回数据看板</el-button>
  </div>
</template>

<style scoped>
.admin-not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 80px 24px;
  text-align: center;
}

.admin-not-found strong {
  font-size: 3rem;
  font-weight: 800;
  color: var(--text-muted);
  line-height: 1;
}

.admin-not-found p {
  color: var(--text-secondary);
  font-size: 0.875rem;
}
</style>
