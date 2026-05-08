<script setup>
import AppIcon from '../../ui/AppIcon.vue';

defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  compact: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="ops-status-band" :class="{ 'is-compact': compact }">
    <article
      v-for="item in items"
      :key="item.key || item.id || item.label"
      class="ops-status-band__item"
      :class="item.tone ? `is-${item.tone}` : ''"
    >
      <div class="ops-status-band__head">
        <span class="ops-status-band__label">{{ item.label }}</span>
        <span v-if="item.icon" class="ops-status-band__icon" aria-hidden="true">
          <AppIcon :name="item.icon" />
        </span>
      </div>
      <strong class="ops-status-band__value">{{ item.value }}</strong>
      <p v-if="item.note || item.detail" class="ops-status-band__note">{{ item.note || item.detail }}</p>
    </article>
  </section>
</template>

<style scoped>
.ops-status-band {
  display: grid;
  grid-template-columns: repeat(var(--band-columns, 4), minmax(0, 1fr));
  gap: 0;
  border: 1px solid var(--line-soft);
  border-radius: 24px;
  background: var(--surface-1);
  overflow: hidden;
}

.ops-status-band__item {
  display: grid;
  gap: 6px;
  padding: 18px 20px;
  min-height: 118px;
  border-left: 1px solid var(--line-soft);
  background: transparent;
}

.ops-status-band__item:first-child {
  border-left: 0;
}

.ops-status-band__item.is-risk {
  background: linear-gradient(180deg, rgba(196, 73, 61, 0.08), transparent);
}

.ops-status-band__item.is-warning {
  background: linear-gradient(180deg, rgba(183, 121, 31, 0.08), transparent);
}

.ops-status-band__item.is-brand {
  background: linear-gradient(180deg, rgba(36, 87, 197, 0.1), transparent);
}

.ops-status-band__item.is-accent {
  background: linear-gradient(180deg, rgba(64, 157, 157, 0.09), transparent);
}

.ops-status-band__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.ops-status-band__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ops-status-band__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 1px solid rgba(157, 173, 196, 0.18);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-primary);
}

.ops-status-band__value {
  color: var(--text-primary);
  font-size: clamp(1.3rem, 2.1vw, 1.8rem);
  line-height: 1.05;
  letter-spacing: -0.05em;
}

.ops-status-band__note {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.8125rem;
  line-height: 1.7;
}

.ops-status-band.is-compact .ops-status-band__item {
  gap: 4px;
  min-height: 92px;
  padding: 14px 16px;
}

.ops-status-band.is-compact .ops-status-band__icon {
  width: 28px;
  height: 28px;
  border-radius: 10px;
}

.ops-status-band.is-compact .ops-status-band__value {
  font-size: clamp(1.15rem, 1.6vw, 1.45rem);
  letter-spacing: -0.04em;
}

.ops-status-band.is-compact .ops-status-band__note {
  font-size: 0.75rem;
  line-height: 1.5;
}

@media (max-width: 1120px) {
  .ops-status-band {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-status-band__item:nth-child(odd) {
    border-left: 0;
  }

  .ops-status-band__item:nth-child(n + 3) {
    border-top: 1px solid var(--line-soft);
  }
}

@media (max-width: 720px) {
  .ops-status-band {
    grid-template-columns: 1fr;
  }

  .ops-status-band__item {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
  }

  .ops-status-band__item:first-child {
    border-top: 0;
  }
}
</style>
