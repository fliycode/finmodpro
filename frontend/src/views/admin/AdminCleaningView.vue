<script setup>
import { ref } from 'vue';
</script>

<template>
  <section class="cleaning-view">
    <div class="cleaning-view__placeholder">
      <h2>数据清洗</h2>
      <p>配置清洗规则、查看清洗质量与问题报告。</p>
      <p class="cleaning-view__status">功能开发中...</p>
    </div>
  </section>
</template>

<style scoped>
.cleaning-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 400px;
}

.cleaning-view__placeholder {
  text-align: center;
  padding: 40px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-card);
  max-width: 480px;
}

.cleaning-view__placeholder h2 {
  margin: 0 0 12px;
  color: var(--text-primary);
  font-size: 1.5rem;
}

.cleaning-view__placeholder p {
  margin: 0 0 8px;
  color: var(--text-muted);
}

.cleaning-view__status {
  color: var(--brand);
  font-weight: 600;
}
</style>
