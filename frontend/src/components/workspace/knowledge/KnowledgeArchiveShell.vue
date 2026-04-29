<template>
  <section class="knowledge-archive-shell">
    <header class="knowledge-archive-shell__filters">
      <slot name="filters" />
    </header>

    <div class="knowledge-archive-shell__grid">
      <section class="knowledge-archive-shell__ledger">
        <slot name="ledger" />
      </section>
      <aside class="knowledge-archive-shell__inspector">
        <slot name="inspector" />
      </aside>
    </div>
  </section>
</template>

<style scoped>
.knowledge-archive-shell {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-height: 0;
}

.knowledge-archive-shell__filters,
.knowledge-archive-shell__ledger,
.knowledge-archive-shell__inspector {
  min-height: 0;
}

.knowledge-archive-shell__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(320px, 0.85fr);
  gap: 18px;
  min-height: 0;
}

@media (max-width: 1180px) {
  .knowledge-archive-shell__grid {
    grid-template-columns: 1fr;
  }
}
</style>
