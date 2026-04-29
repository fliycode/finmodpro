<template>
  <section class="dossier-evidence-stack">
    <slot />
  </section>
</template>

<style scoped>
.dossier-evidence-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
  min-height: 0;
}
</style>
