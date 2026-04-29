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
  border: 1px solid rgba(95, 123, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(10, 18, 31, 0.92), rgba(8, 14, 26, 0.92)),
    radial-gradient(circle at top right, rgba(89, 100, 255, 0.1), transparent 40%);
  box-shadow: 0 22px 56px -42px rgba(3, 9, 22, 0.94);
  backdrop-filter: blur(18px);
  overflow: hidden;
}

.evidence-rail__header {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 18px 18px 16px;
  border-bottom: 1px solid rgba(95, 123, 255, 0.12);
}

.evidence-rail__eyebrow {
  margin: 0 0 5px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7c93bb;
}

.evidence-rail h2 {
  margin: 0;
  font-size: 20px;
  line-height: 1.2;
  color: #eef4ff;
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
  border: 1px solid rgba(93, 130, 255, 0.2);
  background: rgba(49, 68, 130, 0.22);
  color: #a9beff;
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
