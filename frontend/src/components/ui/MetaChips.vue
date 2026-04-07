<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
});
</script>

<template>
  <div v-if="items.length" class="meta-chip-row">
    <span v-for="item in items" :key="item.key || item.label" class="meta-chip" :title="item.title || item.label">
      {{ item.label }}
    </span>
  </div>
</template>
