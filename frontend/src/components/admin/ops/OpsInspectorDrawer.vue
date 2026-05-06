<script setup>
defineProps({
  title: {
    type: String,
    default: '',
  },
  desc: {
    type: String,
    default: '',
  },
});
</script>

<template>
  <section class="ops-inspector-drawer">
    <header v-if="title || desc" class="ops-inspector-drawer__header">
      <div>
        <p class="ops-inspector-drawer__eyebrow">Inspector</p>
        <h2 v-if="title" class="ops-inspector-drawer__title">{{ title }}</h2>
        <p v-if="desc" class="ops-inspector-drawer__desc">{{ desc }}</p>
      </div>
      <div v-if="$slots.header" class="ops-inspector-drawer__meta">
        <slot name="header" />
      </div>
    </header>
    <div class="ops-inspector-drawer__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.ops-inspector-drawer {
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 22px 24px;
  border: 1px solid var(--line-soft);
  border-radius: 28px;
  background:
    linear-gradient(180deg, rgba(15, 21, 30, 0.95), rgba(10, 15, 22, 0.92));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.ops-inspector-drawer__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.ops-inspector-drawer__eyebrow {
  margin: 0 0 6px;
  font-size: 0.6875rem;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ops-inspector-drawer__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1.15rem;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.ops-inspector-drawer__desc {
  margin: 8px 0 0;
  color: var(--text-secondary);
  line-height: 1.55;
}

.ops-inspector-drawer__body {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

@media (max-width: 720px) {
  .ops-inspector-drawer__header {
    flex-direction: column;
  }
}
</style>
