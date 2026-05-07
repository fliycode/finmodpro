<script setup>
import { computed } from 'vue';
import { RouterLink, useRoute } from 'vue-router';

const props = defineProps({
  statusItems: {
    type: Array,
    default: () => [],
  },
});

const route = useRoute();
const navItems = [
  { id: 'query', label: '查询工作台', to: '/admin/lightrag/query' },
  { id: 'graph', label: '图谱浏览', to: '/admin/lightrag/graph' },
  { id: 'documents', label: '文档管线', to: '/admin/lightrag/documents' },
];

const railItems = computed(() => props.statusItems.filter((item) => item?.label));
const isActive = (item) => route.path === item.to;
</script>

<template>
  <div class="page-stack lightrag-workspace-shell">
    <section v-if="$slots.aside || $slots.actions" class="lightrag-workspace-shell__toolbar">
      <div class="lightrag-workspace-shell__meta">
        <div v-if="$slots.aside" class="lightrag-workspace-shell__aside">
          <slot name="aside" />
        </div>
        <div v-if="$slots.actions" class="lightrag-workspace-shell__actions">
          <slot name="actions" />
        </div>
      </div>
    </section>

    <nav class="lightrag-workspace-shell__nav" aria-label="Graph workspace sections">
      <RouterLink
        v-for="item in navItems"
        :key="item.id"
        :to="item.to"
        :class="['lightrag-workspace-shell__nav-item', { 'lightrag-workspace-shell__nav-item--active': isActive(item) }]"
      >
        {{ item.label }}
      </RouterLink>
    </nav>

    <section v-if="railItems.length" class="lightrag-workspace-shell__rail">
      <article
        v-for="item in railItems"
        :key="item.label"
        class="lightrag-workspace-shell__rail-item"
      >
        <span class="lightrag-workspace-shell__rail-label">{{ item.label }}</span>
        <strong class="lightrag-workspace-shell__rail-value">{{ item.value }}</strong>
        <p v-if="item.note" class="lightrag-workspace-shell__rail-note">{{ item.note }}</p>
      </article>
    </section>

    <slot />
  </div>
</template>

<style scoped>
.lightrag-workspace-shell {
  min-width: 0;
}

.lightrag-workspace-shell__toolbar {
  display: flex;
  justify-content: flex-end;
}

.lightrag-workspace-shell__rail-label {
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.lightrag-workspace-shell__rail-note {
  max-width: 72ch;
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.65;
}

.lightrag-workspace-shell__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
  align-items: center;
  justify-content: space-between;
}

.lightrag-workspace-shell__aside {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--text-secondary);
  font-size: 0.8125rem;
}

.lightrag-workspace-shell__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: flex-end;
  align-items: center;
}

.lightrag-workspace-shell__nav {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.lightrag-workspace-shell__nav-item {
  display: inline-flex;
  align-items: center;
  min-height: 40px;
  padding: 0 16px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-secondary);
  text-decoration: none;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
}

.lightrag-workspace-shell__nav-item:hover,
.lightrag-workspace-shell__nav-item--active {
  border-color: rgba(36, 87, 197, 0.26);
  background: var(--brand-soft);
  color: var(--brand);
}

.lightrag-workspace-shell__rail {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.lightrag-workspace-shell__rail-item {
  display: grid;
  gap: 8px;
  padding: 16px 18px;
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
}

.lightrag-workspace-shell__rail-value {
  color: var(--text-primary);
  font-size: 1.15rem;
  line-height: 1.2;
}

@media (max-width: 1180px) {
  .lightrag-workspace-shell__meta,
  .lightrag-workspace-shell__aside {
    justify-content: flex-start;
  }
}

@media (max-width: 900px) {
  .lightrag-workspace-shell__rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .lightrag-workspace-shell__meta {
    align-items: flex-start;
  }

  .lightrag-workspace-shell__rail {
    grid-template-columns: 1fr;
  }
}
</style>
