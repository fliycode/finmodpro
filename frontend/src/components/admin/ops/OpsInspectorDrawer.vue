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
  gap: 14px;
  padding: 18px;
  border: 1px solid rgba(127, 146, 170, 0.16);
  border-radius: 22px;
  background: rgba(10, 16, 24, 0.96);
}

.ops-inspector-drawer__header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.ops-inspector-drawer__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8aa0b8;
}

.ops-inspector-drawer__title {
  margin: 0;
  color: #f3f6fb;
  font-size: 22px;
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.ops-inspector-drawer__desc {
  margin: 8px 0 0;
  color: #9caec1;
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
