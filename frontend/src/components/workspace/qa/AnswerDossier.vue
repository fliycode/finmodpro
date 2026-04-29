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
  border: 1px solid rgba(95, 123, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(12, 20, 36, 0.92), rgba(9, 15, 29, 0.92)),
    radial-gradient(circle at top right, rgba(104, 83, 255, 0.12), transparent 42%);
  box-shadow: 0 22px 58px -40px rgba(3, 9, 22, 0.92);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.answer-dossier__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 22px 22px 18px;
  border-bottom: 1px solid rgba(95, 123, 255, 0.12);
}

.answer-dossier__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7c93bb;
}

.answer-dossier h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: #eef4ff;
}

.answer-dossier__meta {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 11px;
  border-radius: 999px;
  border: 1px solid rgba(93, 130, 255, 0.2);
  background: rgba(49, 68, 130, 0.24);
  color: #a9beff;
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
