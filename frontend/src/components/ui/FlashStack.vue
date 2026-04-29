<script setup>
import { computed } from 'vue';
import { useFlash } from '../../lib/flash.js';
import AppIcon from './AppIcon.vue';

const flash = useFlash();

const iconFor = (type) => {
  if (type === 'success') return 'check';
  if (type === 'error') return 'alert-triangle';
  return 'info';
};
</script>

<template>
  <div v-if="flash.items.length" class="flash-stack">
    <div
      v-for="item in flash.items"
      :key="item.id"
      class="flash-stack__item"
      :class="`is-${item.type}`"
    >
      <AppIcon :name="iconFor(item.type)" />
      <span>{{ item.message }}</span>
      <button type="button" @click="flash.dismiss(item.id)">关闭</button>
    </div>
  </div>
</template>
