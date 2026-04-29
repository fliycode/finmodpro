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
  gap: 16px;
}

.history-workbench__filters,
.history-workbench__records {
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 22px;
  background: rgba(251, 246, 237, 0.94);
  box-shadow: 0 18px 52px -42px rgba(80, 54, 20, 0.28);
}

.history-workbench__filters {
  padding: 20px;
}

.history-workbench__records {
  padding: 18px;
}
</style>
