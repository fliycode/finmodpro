<script setup>
defineProps({
  total: {
    type: Number,
    default: 0,
  },
  activeCount: {
    type: Number,
    default: 0,
  },
  indexedCount: {
    type: Number,
    default: 0,
  },
});
</script>

<template>
  <section class="knowledge-asset-ledger">
    <header class="knowledge-asset-ledger__header">
      <div>
        <p class="knowledge-asset-ledger__eyebrow">Asset ledger</p>
        <h2>知识资产总账</h2>
      </div>
      <div class="knowledge-asset-ledger__stats">
        <span>{{ total }} 份文档</span>
        <span>{{ activeCount }} 项处理中</span>
        <span>{{ indexedCount }} 项可检索</span>
      </div>
    </header>
    <div class="knowledge-asset-ledger__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.knowledge-asset-ledger {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 24px;
  background: rgba(251, 246, 237, 0.94);
  box-shadow: 0 20px 56px -40px rgba(80, 54, 20, 0.28);
  overflow: hidden;
}

.knowledge-asset-ledger__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 22px 16px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.knowledge-asset-ledger__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.knowledge-asset-ledger h2 {
  margin: 0;
  font-size: 24px;
  line-height: 1.15;
  color: #2f2418;
}

.knowledge-asset-ledger__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.knowledge-asset-ledger__stats span {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: rgba(154, 106, 44, 0.1);
  color: #8a6030;
  font-size: 12px;
  font-weight: 700;
}

.knowledge-asset-ledger__body {
  flex: 1;
  min-height: 0;
  padding: 18px;
}

@media (max-width: 720px) {
  .knowledge-asset-ledger__header {
    flex-direction: column;
  }

  .knowledge-asset-ledger__stats {
    justify-content: flex-start;
  }
}
</style>
