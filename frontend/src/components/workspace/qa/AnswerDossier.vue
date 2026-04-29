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
        <h2>结论档案</h2>
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
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 24px;
  background: linear-gradient(180deg, rgba(255, 251, 245, 0.96), rgba(248, 241, 229, 0.96));
  box-shadow: 0 20px 56px -40px rgba(80, 54, 20, 0.32);
  overflow: hidden;
}

.answer-dossier__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 22px 18px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.answer-dossier__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.answer-dossier h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: #2f2418;
}

.answer-dossier__meta {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  background: rgba(154, 106, 44, 0.1);
  color: #8a6030;
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
