<script setup>
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
        <h3 v-if="props.title" class="section-heading__title">{{ props.title }}</h3>
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
          <h3 v-if="props.title" class="section-heading__title">{{ props.title }}</h3>
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
</style>
