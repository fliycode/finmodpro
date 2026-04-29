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
        <h2>证据索引</h2>
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
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 20px;
  background: rgba(248, 241, 229, 0.9);
  box-shadow: 0 18px 48px -38px rgba(80, 54, 20, 0.28);
  overflow: hidden;
}

.evidence-rail__header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.evidence-rail__eyebrow {
  margin: 0 0 5px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.evidence-rail h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  color: #2f2418;
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
  background: rgba(154, 106, 44, 0.08);
  color: #8a6030;
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
