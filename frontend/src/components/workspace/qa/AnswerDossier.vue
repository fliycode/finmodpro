<script setup>
defineProps({
  active: {
    type: Boolean,
    default: false,
  },
  entryCount: {
    type: Number,
    default: 0,
  },
  isEmpty: {
    type: Boolean,
    default: false,
  },
});
</script>

<template>
  <section class="answer-dossier" :class="{ 'is-active': active }">
    <header class="answer-dossier__header">
      <div>
        <p class="answer-dossier__eyebrow">Answer dossier</p>
        <h2>分析摘要</h2>
      </div>
      <span class="answer-dossier__meta">
        {{ isEmpty ? '等待首份结论' : `${entryCount} 份结论` }}
      </span>
    </header>
    <div class="answer-dossier__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.answer-dossier {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.answer-dossier__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 22px 18px;
  border-bottom: 1px solid var(--line-soft);
}

.answer-dossier__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.answer-dossier h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: var(--text-primary);
}

.answer-dossier__meta {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

.answer-dossier__body {
  flex: 1;
  min-height: 0;
}

@media (max-width: 1024px) {
  .answer-dossier {
    display: none;
  }

  .answer-dossier.is-active {
    display: flex;
  }
}
</style>
