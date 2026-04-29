<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <section class="ops-status-band">
    <article
      v-for="item in items"
      :key="item.key || item.id || item.label"
      class="ops-status-band__item"
      :class="item.tone ? `is-${item.tone}` : ''"
    >
      <span class="ops-status-band__label">{{ item.label }}</span>
      <strong class="ops-status-band__value">{{ item.value }}</strong>
      <p v-if="item.note || item.detail" class="ops-status-band__note">{{ item.note || item.detail }}</p>
    </article>
  </section>
</template>

<style scoped>
.ops-status-band {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.ops-status-band__item {
  display: grid;
  gap: 8px;
  padding: 18px;
  border: 1px solid rgba(127, 146, 170, 0.16);
  border-radius: 18px;
  background: rgba(13, 21, 32, 0.94);
  box-shadow: inset 0 1px 0 rgba(196, 208, 224, 0.04);
}

.ops-status-band__item.is-risk {
  border-color: rgba(182, 83, 83, 0.24);
}

.ops-status-band__item.is-warning {
  border-color: rgba(191, 145, 79, 0.24);
}

.ops-status-band__label {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #8aa0b8;
}

.ops-status-band__value {
  color: #f3f6fb;
  font-size: 28px;
  line-height: 1;
  letter-spacing: -0.04em;
}

.ops-status-band__note {
  margin: 0;
  color: #9caec1;
  font-size: 13px;
  line-height: 1.55;
}

@media (max-width: 1120px) {
  .ops-status-band {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .ops-status-band {
    grid-template-columns: 1fr;
  }
}
</style>
