<template>
  <section class="governance-review-desk">
    <aside class="governance-review-desk__queue">
      <slot name="queue" />
    </aside>
    <section class="governance-review-desk__comparison">
      <slot />
    </section>
    <aside class="governance-review-desk__decision">
      <slot name="decision" />
    </aside>
  </section>
</template>

<style scoped>
.governance-review-desk {
  display: grid;
  grid-template-columns: minmax(260px, 0.74fr) minmax(0, 1.45fr) minmax(260px, 0.84fr);
  gap: 18px;
  align-items: start;
}

.governance-review-desk__queue,
.governance-review-desk__comparison,
.governance-review-desk__decision {
  min-width: 0;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  overflow: hidden;
}

.governance-review-desk :deep(.admin-section-card) {
  padding: 22px 24px;
}

.governance-review-desk :deep(.admin-section-card + .admin-section-card) {
  border-top: 1px solid var(--line-soft);
}

@media (max-width: 1280px) {
  .governance-review-desk {
    grid-template-columns: minmax(260px, 0.88fr) minmax(0, 1.12fr);
  }

  .governance-review-desk__decision {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .governance-review-desk {
    grid-template-columns: 1fr;
  }
}
</style>
