<script setup>
defineProps({
  label: { type: String, required: true },
  status: { type: String, default: 'healthy' },
  detail: { type: String, default: '' },
  tone: { type: String, default: 'success' },
  icon: { type: String, default: 'circle' },
});
</script>

<template>
  <div class="service-card" :class="`tone-${tone}`">
    <div class="service-card__icon">
      <span class="service-card__dot" />
    </div>
    <div class="service-card__body">
      <span class="service-card__label">{{ label }}</span>
      <span class="service-card__detail">{{ detail }}</span>
    </div>
  </div>
</template>

<style scoped>
.service-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  border-radius: 12px;
  background: var(--surface-1, #fff);
  border: 1px solid var(--line-soft, #e5e7eb);
  transition: border-color 0.2s;
}

.service-card__icon {
  flex-shrink: 0;
}

.service-card__dot {
  display: block;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--success, #22c55e);
}

.tone-risk .service-card__dot {
  background: var(--risk, #ef4444);
}

.tone-warning .service-card__dot {
  background: var(--warning, #f59e0b);
}

.service-card__body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.service-card__label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #111827);
}

.service-card__detail {
  font-size: 12px;
  color: var(--text-secondary, #6b7280);
}
</style>
