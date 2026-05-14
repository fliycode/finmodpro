<script setup>
import AppIcon from '../../ui/AppIcon.vue';

const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  eyebrow: {
    type: String,
    default: 'Inspector',
  },
  desc: {
    type: String,
    default: '',
  },
  icon: {
    type: String,
    default: '',
  },
});
</script>

<template>
  <section class="ops-inspector-drawer">
    <header v-if="props.title || props.desc || props.eyebrow" class="ops-inspector-drawer__header">
      <div>
        <p v-if="props.eyebrow" class="ops-inspector-drawer__eyebrow">{{ props.eyebrow }}</p>
        <div v-if="props.title" class="ops-inspector-drawer__title-row">
          <span v-if="props.icon" class="ops-inspector-drawer__icon" aria-hidden="true">
            <AppIcon :name="props.icon" />
          </span>
          <h2 class="ops-inspector-drawer__title">{{ props.title }}</h2>
        </div>
        <p v-if="props.desc" class="ops-inspector-drawer__desc">{{ props.desc }}</p>
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

.ops-inspector-drawer__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ops-inspector-drawer__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid rgba(157, 173, 196, 0.18);
  border-radius: 10px;
  color: var(--text-primary);
  background: rgba(255, 255, 255, 0.04);
  flex-shrink: 0;
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
