<script setup>
defineProps({
  eyebrow: {
    type: String,
    default: '',
  },
  title: {
    type: String,
    default: '',
  },
  summary: {
    type: String,
    default: '',
  },
  meta: {
    type: Array,
    default: () => [],
  },
  tone: {
    type: String,
    default: 'neutral',
  },
});
</script>

<template>
  <section class="ops-section-frame" :class="`is-${tone}`">
    <header v-if="meta.length || $slots.actions" class="ops-section-frame__header">
      <div v-if="meta.length" class="ops-section-frame__meta">
        <span v-for="item in meta" :key="item">{{ item }}</span>
      </div>
      <div v-if="$slots.actions" class="ops-section-frame__actions">
        <slot name="actions" />
      </div>
    </header>

    <div v-if="$slots.alerts" class="ops-section-frame__alerts">
      <slot name="alerts" />
    </div>

    <div v-if="$slots['status-band']" class="ops-section-frame__status-band">
      <slot name="status-band" />
    </div>

    <div class="ops-section-frame__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.ops-section-frame {
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--text-secondary);
}

.ops-section-frame__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-1);
}

.ops-section-frame.is-risk .ops-section-frame__header {
  border-color: rgba(214, 85, 108, 0.24);
}

.ops-section-frame.is-warning .ops-section-frame__header {
  border-color: rgba(255, 179, 71, 0.24);
}

.ops-section-frame__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ops-section-frame__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  padding: 0 10px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: 0.6875rem;
}

.ops-section-frame__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  min-width: 200px;
}

.ops-section-frame__alerts,
.ops-section-frame__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

@media (max-width: 900px) {
  .ops-section-frame__header {
    flex-direction: column;
  }

  .ops-section-frame__actions {
    min-width: 0;
    justify-content: flex-start;
  }
}
</style>
