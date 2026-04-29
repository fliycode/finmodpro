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
  gap: 16px;
  align-items: start;
}

.governance-review-desk__queue,
.governance-review-desk__comparison,
.governance-review-desk__decision {
  min-width: 0;
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
