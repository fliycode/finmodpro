<script setup>
defineProps({
  title: {
    type: String,
    required: true,
  },
  eyebrow: {
    type: String,
    default: 'Dossier page',
  },
});
</script>

<template>
  <section class="dossier-page-shell">
    <div class="dossier-page-shell__grid">
      <section class="dossier-page-shell__summary">
        <slot name="summary" />
      </section>
      <section class="dossier-page-shell__evidence">
        <slot name="evidence" />
      </section>
      <aside class="dossier-page-shell__actions">
        <slot name="actions" />
      </aside>
    </div>
  </section>
</template>

<style scoped>
.dossier-page-shell {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.dossier-page-shell__grid {
  display: grid;
  grid-template-columns: minmax(0, 0.92fr) minmax(0, 1.08fr) minmax(280px, 0.82fr);
  gap: 20px;
  min-height: 0;
}

.dossier-page-shell__summary,
.dossier-page-shell__evidence,
.dossier-page-shell__actions {
  min-height: 0;
}

@media (max-width: 1280px) {
  .dossier-page-shell__grid {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  }

  .dossier-page-shell__actions {
    grid-column: 1 / -1;
  }
}

@media (max-width: 920px) {
  .dossier-page-shell__grid {
    grid-template-columns: 1fr;
    display: block;
  }

  .dossier-page-shell__summary,
  .dossier-page-shell__evidence,
  .dossier-page-shell__actions {
    margin-top: 18px;
  }
}
</style>
