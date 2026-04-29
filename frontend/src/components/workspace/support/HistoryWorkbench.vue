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
  border: 1px solid rgba(96, 126, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(13, 22, 38, 0.9), rgba(10, 17, 31, 0.92)),
    radial-gradient(circle at top right, rgba(90, 106, 255, 0.12), transparent 38%);
  box-shadow: 0 24px 58px -42px rgba(4, 10, 22, 0.96);
}

.history-workbench__filters {
  padding: 20px;
}

.history-workbench__records {
  padding: 18px;
}
</style>
