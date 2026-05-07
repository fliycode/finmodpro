<script setup>
const props = defineProps({
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
  <section class="ops-section-frame" :class="`is-${props.tone}`">
    <header
      v-if="props.meta.length || $slots.actions"
      class="ops-section-frame__toolbar"
    >
      <div class="ops-section-frame__rail">
        <div v-if="props.meta.length" class="ops-section-frame__meta">
          <span v-for="item in props.meta" :key="item">{{ item }}</span>
        </div>
        <div v-if="$slots.actions" class="ops-section-frame__actions">
          <slot name="actions" />
        </div>
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
  gap: 14px;
  color: var(--text-secondary);
}

.ops-section-frame__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  min-width: 0;
}

.ops-section-frame__rail {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  width: 100%;
  min-width: 0;
  align-items: center;
  justify-content: space-between;
}

.ops-section-frame__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.ops-section-frame__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: var(--surface-2);
  color: var(--text-primary);
  font-size: 0.6875rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.ops-section-frame__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.ops-section-frame__alerts,
.ops-section-frame__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 900px) {
  .ops-section-frame__rail,
  .ops-section-frame__actions,
  .ops-section-frame__meta {
    min-width: 0;
    justify-content: flex-start;
    align-items: flex-start;
  }
}
</style>
