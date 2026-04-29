<template>
  <section class="ops-command-deck">
    <slot />
  </section>
</template>

<style scoped>
.ops-command-deck {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

@media (max-width: 900px) {
  .ops-command-deck {
    grid-template-columns: 1fr;
  }
}
</style>
