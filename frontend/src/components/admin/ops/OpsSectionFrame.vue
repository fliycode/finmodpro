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
      v-if="props.eyebrow || props.title || props.summary || props.meta.length || $slots.actions"
      class="ops-section-frame__hero"
    >
      <div v-if="props.eyebrow || props.title || props.summary" class="ops-section-frame__heading">
        <p v-if="props.eyebrow" class="ops-section-frame__eyebrow">{{ props.eyebrow }}</p>
        <h2 v-if="props.title" class="ops-section-frame__title">{{ props.title }}</h2>
        <p v-if="props.summary" class="ops-section-frame__summary">{{ props.summary }}</p>
      </div>

      <div v-if="props.meta.length || $slots.actions" class="ops-section-frame__rail">
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
  gap: 16px;
  color: var(--text-secondary);
}

.ops-section-frame__hero {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
  padding: 26px 28px 22px;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.ops-section-frame.is-risk .ops-section-frame__hero {
  border-color: rgba(214, 85, 108, 0.24);
}

.ops-section-frame.is-warning .ops-section-frame__hero {
  border-color: rgba(255, 179, 71, 0.24);
}

.ops-section-frame__heading {
  display: grid;
  gap: 10px;
  min-width: 0;
  max-width: 820px;
}

.ops-section-frame__eyebrow {
  margin: 0;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ops-section-frame__title {
  margin: 0;
  color: var(--text-primary);
  font-size: clamp(1.8rem, 3vw, 2.6rem);
  line-height: 1.04;
  letter-spacing: -0.04em;
}

.ops-section-frame__summary {
  margin: 0;
  max-width: 64ch;
  color: var(--text-secondary);
  line-height: 1.72;
}

.ops-section-frame__rail {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-width: 320px;
  align-items: flex-end;
}

.ops-section-frame__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}

.ops-section-frame__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 12px;
  border: 1px solid var(--line-soft);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.02);
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
  justify-content: flex-end;
}

.ops-section-frame__alerts,
.ops-section-frame__body {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 900px) {
  .ops-section-frame__hero {
    flex-direction: column;
    padding: 22px 20px 18px;
  }

  .ops-section-frame__rail,
  .ops-section-frame__actions,
  .ops-section-frame__meta {
    min-width: 0;
    justify-content: flex-start;
    align-items: flex-start;
  }
}
</style>
