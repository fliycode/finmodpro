<script setup>
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const route = useRoute();

const tabs = [
  { id: 'overview', label: '模型总览', to: '/admin/llm/models' },
  { id: 'logs', label: '模型日志', to: '/admin/llm/logs' },
  { id: 'usage', label: '用量统计', to: '/admin/llm/usage' },
];

const isActive = computed(() => (target) => route.path === target);
</script>

<template>
  <nav class="llm-management-tabs" aria-label="模型管理分栏">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.id"
      :to="tab.to"
      :class="['llm-management-tabs__item', { 'llm-management-tabs__item--active': isActive(tab.to) }]"
    >
      {{ tab.label }}
    </RouterLink>
  </nav>
</template>

<style scoped>
.llm-management-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  padding: 4px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: rgba(11, 17, 26, 0.6);
}

.llm-management-tabs__item {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0 16px;
  border-radius: 14px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 0.9375rem;
  font-weight: 600;
  transition: background-color 0.2s ease, color 0.2s ease, transform 0.2s ease;
}

.llm-management-tabs__item:hover {
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.llm-management-tabs__item:focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 2px;
}

.llm-management-tabs__item--active {
  background: rgba(213, 164, 65, 0.16);
  color: var(--text-primary);
}
</style>
