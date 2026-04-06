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
  <el-card :class="['ui-card', admin ? 'ui-card--admin admin-section-card' : 'admin-section-card']" :shadow="shadow">
    <template #header>
      <div class="section-heading">
        <h3 v-if="title" class="section-heading__title">{{ title }}</h3>
        <div v-if="desc" class="section-heading__desc">{{ desc }}</div>
        <slot name="header" />
      </div>
    </template>

    <slot />
  </el-card>
</template>
