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
    <header class="ops-section-frame__header">
      <div class="ops-section-frame__copy">
        <p v-if="eyebrow" class="ops-section-frame__eyebrow">{{ eyebrow }}</p>
        <h1 v-if="title" class="ops-section-frame__title">{{ title }}</h1>
        <p v-if="summary" class="ops-section-frame__summary">{{ summary }}</p>
        <div v-if="meta.length" class="ops-section-frame__meta">
          <span v-for="item in meta" :key="item">{{ item }}</span>
        </div>
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
  gap: 20px;
  color: #dbe7ff;
}

.ops-section-frame__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 26px;
  border: 1px solid rgba(102, 129, 255, 0.18);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(12, 20, 36, 0.98), rgba(8, 14, 26, 0.96)),
    radial-gradient(circle at top right, rgba(88, 112, 255, 0.16), transparent 38%);
  box-shadow: 0 26px 68px -50px rgba(2, 8, 20, 0.94);
}

.ops-section-frame.is-risk .ops-section-frame__header {
  border-color: rgba(214, 85, 108, 0.24);
}

.ops-section-frame.is-warning .ops-section-frame__header {
  border-color: rgba(255, 179, 71, 0.24);
}

.ops-section-frame__copy {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.ops-section-frame__eyebrow {
  margin: 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8398c2;
}

.ops-section-frame__title {
  margin: 0;
  color: #f4f8ff;
  font-size: 34px;
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.ops-section-frame__summary {
  margin: 0;
  max-width: 760px;
  color: #93a8cb;
  line-height: 1.6;
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
  border: 1px solid rgba(127, 146, 170, 0.18);
  border-radius: 999px;
  background: rgba(15, 24, 42, 0.84);
  color: #d7e5ff;
  font-size: 12px;
}

.ops-section-frame__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-start;
  justify-content: flex-end;
  min-width: 240px;
}

.ops-section-frame__alerts,
.ops-section-frame__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
