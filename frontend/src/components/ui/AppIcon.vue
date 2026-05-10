<script setup>
import { Icon } from '@iconify/vue';

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
});

/** Iconify Lucide icon mappings. Add new icons here as needed. */
const iconMap = {
  // Navigation — workspace
  'spark': 'lucide:sparkle',
  'message-square': 'lucide:message-square',
  'database': 'lucide:library',
  'history': 'lucide:clock',
  'shield': 'lucide:shield-alert',
  'trending-up': 'lucide:trending-up',
  'user': 'lucide:user',
  // Navigation — admin
  'dashboard': 'lucide:gauge',
  'layout-dashboard': 'lucide:gauge',
  'users': 'lucide:users',
  'network': 'lucide:network',
  'brain-circuit': 'lucide:brain-circuit',
  'bar-chart': 'lucide:bar-chart-3',
  'microscope': 'lucide:microscope',
  // UI / Actions
  'sliders': 'lucide:sliders-horizontal',
  'beaker': 'lucide:flask-conical',
  'eye': 'lucide:eye',
  'eye-off': 'lucide:eye-off',
  'send': 'lucide:send',
  'moon': 'lucide:moon',
  'sun': 'lucide:sun',
  'search': 'lucide:search',
  'plus': 'lucide:plus',
  'play': 'lucide:play',
  'x': 'lucide:x',
  'external-link': 'lucide:external-link',
  'alert-triangle': 'lucide:alert-triangle',
  'check': 'lucide:check',
  'info': 'lucide:info',
  'download': 'lucide:download',
  'upload': 'lucide:upload',
  'trash': 'lucide:trash-2',
  'edit': 'lucide:pencil',
  'settings': 'lucide:settings',
  'filter': 'lucide:list-filter',
  'refresh': 'lucide:refresh-cw',
  'mouse-pointer-click': 'lucide:mouse-pointer-click',
  'copy': 'lucide:copy',
  'tag': 'lucide:tag',
  'book-open': 'lucide:book-open',
  'file-text': 'lucide:file-text',
  // Logos
  'github': 'lucide:github',
  // QA / Chat
  'mic': 'lucide:mic',
  'zap': 'lucide:zap',
  'file': 'lucide:file-text',
  'clipboard': 'lucide:scroll-text',
  'pie-chart': 'lucide:chart-pie',
  'layers': 'lucide:layers-3',
  'home': 'lucide:home',
  'message-circle': 'lucide:message-circle',
  'globe': 'lucide:globe',
  // Direction
  'chevron-down': 'lucide:chevron-down',
  'chevron-right': 'lucide:chevron-right',
  'arrow-right': 'lucide:arrow-right',
  // Layout
  'menu': 'lucide:menu',
};

const resolvedIcon = iconMap[props.name] || null;
</script>

<template>
  <Icon
    v-if="resolvedIcon"
    :icon="resolvedIcon"
    class="app-icon"
    :aria-label="props.name"
    role="img"
    width="18"
    height="18"
  />
  <svg
    v-else
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    :aria-label="props.name"
    role="img"
    width="18"
    height="18"
  >
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4l2.5 2.5" />
  </svg>
</template>
