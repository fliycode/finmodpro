<template>
  <section class="history-workbench">
    <header class="history-workbench__filters">
      <slot name="filters" />
    </header>
    <section class="history-workbench__records">
      <slot />
    </section>
  </section>
</template>

<style scoped>
.history-workbench {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-workbench__filters,
.history-workbench__records {
  border: 1px solid var(--line-soft);
  border-radius: 6px;
  background: var(--surface-2);
}

.history-workbench__filters {
  padding: 16px 18px;
}

.history-workbench__records {
  padding: 16px;
}
</style>
