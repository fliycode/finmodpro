<script setup>
defineProps({
  active: {
    type: Boolean,
    default: false,
  },
  citationCount: {
    type: Number,
    default: 0,
  },
  historyCount: {
    type: Number,
    default: 0,
  },
});
</script>

<template>
  <aside class="evidence-rail" :class="{ 'is-active': active }">
    <header class="evidence-rail__header">
      <div>
        <p class="evidence-rail__eyebrow">Evidence rail</p>
        <h2>引用与线索</h2>
      </div>
      <div class="evidence-rail__meta">
        <span>{{ citationCount }} 条依据</span>
        <span>{{ historyCount }} 条历史</span>
      </div>
    </header>
    <div class="evidence-rail__body">
      <slot />
    </div>
  </aside>
</template>

<style scoped>
.evidence-rail {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.evidence-rail__header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid var(--line-soft);
}

.evidence-rail__eyebrow {
  margin: 0 0 5px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.evidence-rail h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  color: var(--text-primary);
}

.evidence-rail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.evidence-rail__meta span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

.evidence-rail__body {
  flex: 1;
  min-height: 0;
}

@media (max-width: 1024px) {
  .evidence-rail {
    display: none;
  }

  .evidence-rail.is-active {
    display: flex;
  }
}
</style>
