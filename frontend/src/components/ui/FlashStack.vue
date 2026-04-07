<script setup>
import { useFlash } from '../../lib/flash.js';

const flash = useFlash();
</script>

<template>
  <div v-if="flash.items.length" class="flash-stack">
    <div
      v-for="item in flash.items"
      :key="item.id"
      class="flash-stack__item"
      :class="`is-${item.type}`"
    >
      <span>{{ item.message }}</span>
      <button type="button" @click="flash.dismiss(item.id)">关闭</button>
    </div>
  </div>
</template>
