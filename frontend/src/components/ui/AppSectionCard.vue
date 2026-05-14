<script setup>
import AppIcon from './AppIcon.vue';

const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  desc: {
    type: String,
    default: '',
  },
  admin: {
    type: Boolean,
    default: false,
  },
  icon: {
    type: String,
    default: '',
  },
  shadow: {
    type: String,
    default: 'never',
  },
});
</script>

<template>
  <section v-if="props.admin" class="admin-section-card">
    <header v-if="props.title || props.desc || $slots.header" class="section-heading section-heading--card">
      <div class="section-heading__main">
        <div v-if="props.title" class="section-heading__title-row">
          <span v-if="props.icon" class="section-heading__icon" aria-hidden="true">
            <AppIcon :name="props.icon" />
          </span>
          <h3 class="section-heading__title">{{ props.title }}</h3>
        </div>
        <div v-if="props.desc" class="section-heading__desc">{{ props.desc }}</div>
      </div>
      <div v-if="$slots.header" class="section-heading__meta">
        <slot name="header" />
      </div>
    </header>

    <div class="admin-section-card__body">
      <slot />
    </div>
  </section>

  <el-card v-else :class="['ui-card', 'admin-section-card']" :shadow="props.shadow">
    <template #header>
      <div class="section-heading section-heading--card">
        <div class="section-heading__main">
          <div v-if="props.title" class="section-heading__title-row">
            <span v-if="props.icon" class="section-heading__icon" aria-hidden="true">
              <AppIcon :name="props.icon" />
            </span>
            <h3 class="section-heading__title">{{ props.title }}</h3>
          </div>
          <div v-if="props.desc" class="section-heading__desc">{{ props.desc }}</div>
        </div>
        <div v-if="$slots.header" class="section-heading__meta">
          <slot name="header" />
        </div>
      </div>
    </template>

    <slot />
  </el-card>
</template>

<style scoped>
.admin-section-card,
.admin-section-card__body {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.section-heading__title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.section-heading__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid var(--line-soft);
  border-radius: 10px;
  color: var(--text-secondary);
  background: var(--surface-2);
  flex-shrink: 0;
}
</style>
