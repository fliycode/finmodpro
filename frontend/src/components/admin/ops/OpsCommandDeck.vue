<template>
  <section class="ops-command-deck">
    <slot />
  </section>
</template>

<style scoped>
.ops-command-deck {
  display: grid;
  grid-template-columns: minmax(0, 1.12fr) minmax(320px, 0.88fr);
  gap: 0;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background: var(--surface-1);
  overflow: hidden;
}

.ops-command-deck :deep(.admin-section-card) {
  min-height: 100%;
  padding: 24px 26px;
  border-left: 1px solid var(--line-soft);
  background: transparent;
}

.ops-command-deck :deep(.admin-section-card:first-child) {
  border-left: 0;
}

@media (max-width: 900px) {
  .ops-command-deck {
    grid-template-columns: 1fr;
  }

  .ops-command-deck :deep(.admin-section-card) {
    border-left: 0;
    border-top: 1px solid var(--line-soft);
  }

  .ops-command-deck :deep(.admin-section-card:first-child) {
    border-top: 0;
  }
}
</style>
