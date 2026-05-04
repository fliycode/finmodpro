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
  <section class="lightrag-panel">
    <header v-if="title || desc || $slots.header" class="lightrag-panel__header">
      <div class="lightrag-panel__heading">
        <h3 v-if="title" class="lightrag-panel__title">{{ title }}</h3>
        <p v-if="desc" class="lightrag-panel__desc">{{ desc }}</p>
      </div>
      <div v-if="$slots.header" class="lightrag-panel__actions">
        <slot name="header" />
      </div>
    </header>

    <div class="lightrag-panel__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.lightrag-panel {
  border: 1px solid var(--line-soft);
  border-radius: 18px;
  background: var(--surface-2);
  box-shadow: var(--shadow-sm);
}

.lightrag-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 20px 0;
}

.lightrag-panel__heading {
  display: grid;
  gap: 4px;
}

.lightrag-panel__title {
  margin: 0;
  color: var(--text-primary);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: -0.01em;
}

.lightrag-panel__desc {
  margin: 0;
  color: var(--text-secondary);
  font-size: 0.875rem;
  line-height: 1.5;
}

.lightrag-panel__actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.lightrag-panel__body {
  padding: 18px 20px 20px;
}
</style>
