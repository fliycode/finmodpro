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
  gap: 18px;
  color: #d7e0ea;
}

.ops-section-frame__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  padding: 24px 26px;
  border: 1px solid rgba(127, 146, 170, 0.18);
  border-radius: 24px;
  background:
    linear-gradient(180deg, rgba(17, 24, 34, 0.98), rgba(12, 18, 27, 0.98)),
    radial-gradient(circle at top right, rgba(92, 125, 160, 0.18), transparent 36%);
  box-shadow: 0 30px 70px -54px rgba(3, 8, 15, 0.92);
}

.ops-section-frame.is-risk .ops-section-frame__header {
  border-color: rgba(182, 83, 83, 0.22);
}

.ops-section-frame.is-warning .ops-section-frame__header {
  border-color: rgba(191, 145, 79, 0.22);
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
  color: #8aa0b8;
}

.ops-section-frame__title {
  margin: 0;
  color: #f3f6fb;
  font-size: 34px;
  line-height: 1.02;
  letter-spacing: -0.04em;
}

.ops-section-frame__summary {
  margin: 0;
  max-width: 760px;
  color: #a6b6c8;
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
  background: rgba(24, 33, 46, 0.94);
  color: #d7e0ea;
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
