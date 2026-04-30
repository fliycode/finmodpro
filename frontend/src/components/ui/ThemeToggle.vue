<script setup>
import { computed, onMounted, ref } from 'vue';

import { applyTheme, getStoredTheme, getSystemTheme, persistTheme } from '../../lib/theme.js';
import AppIcon from './AppIcon.vue';

const activeTheme = ref('light');
const isAnimating = ref(false);
let animationTimer = null;

const isDark = computed(() => activeTheme.value === 'dark');
const nextTheme = computed(() => (isDark.value ? 'light' : 'dark'));
const toggleLabel = computed(() => (isDark.value ? '切换到白天模式' : '切换到黑夜模式'));

const syncTheme = (theme) => {
  activeTheme.value = applyTheme(theme);
};

const toggleTheme = () => {
  const selectedTheme = persistTheme(nextTheme.value);
  syncTheme(selectedTheme);
  isAnimating.value = false;
  window.clearTimeout(animationTimer);
  document.documentElement.classList.add('theme-switching');
  requestAnimationFrame(() => {
    isAnimating.value = true;
    animationTimer = window.setTimeout(() => {
      isAnimating.value = false;
      document.documentElement.classList.remove('theme-switching');
    }, 720);
  });
};

onMounted(() => {
  syncTheme(getStoredTheme() || getSystemTheme());
});
</script>

<template>
  <button
    class="theme-toggle"
    :class="{
      'theme-toggle--dark': isDark,
      'theme-toggle--animating': isAnimating,
    }"
    type="button"
    :aria-pressed="isDark"
    :aria-label="toggleLabel"
    :title="toggleLabel"
    @click="toggleTheme"
  >
    <span class="theme-toggle__wash" aria-hidden="true" />
    <span class="theme-toggle__track" aria-hidden="true">
      <span class="theme-toggle__celestial theme-toggle__moon">
        <AppIcon name="moon" />
      </span>
      <span class="theme-toggle__celestial theme-toggle__sun">
        <AppIcon name="sun" />
      </span>
      <span class="theme-toggle__thumb" />
    </span>
  </button>
</template>
