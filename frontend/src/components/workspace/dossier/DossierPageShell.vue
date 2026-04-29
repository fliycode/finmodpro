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
    <header class="dossier-page-shell__header">
      <div>
        <p class="dossier-page-shell__eyebrow">{{ eyebrow }}</p>
        <h2>{{ title }}</h2>
      </div>
      <slot name="header-meta" />
    </header>

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
  gap: 20px;
  min-height: 0;
}

.dossier-page-shell__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid rgba(110, 145, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(13, 22, 37, 0.96), rgba(9, 16, 29, 0.94)),
    radial-gradient(circle at top right, rgba(92, 116, 255, 0.18), transparent 42%);
  box-shadow: 0 20px 48px -30px rgba(4, 10, 22, 0.76);
}

.dossier-page-shell__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7f95bf;
}

.dossier-page-shell h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.06;
  letter-spacing: -0.03em;
  color: #edf4ff;
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
  .dossier-page-shell__header,
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
