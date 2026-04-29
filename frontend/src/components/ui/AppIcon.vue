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
  'spark': 'lucide:sparkles',
  'message-square': 'lucide:message-square',
  'database': 'lucide:database',
  'history': 'lucide:clock-arrow-up',
  'shield': 'lucide:shield-check',
  'trending-up': 'lucide:trending-up',
  'user': 'lucide:user',
  // Navigation — admin
  'dashboard': 'lucide:layout-dashboard',
  'layout-dashboard': 'lucide:layout-dashboard',
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
  'copy': 'lucide:copy',
  'tag': 'lucide:tag',
  'book-open': 'lucide:book-open',
  'file-text': 'lucide:file-text',
  // Logos
  'github': 'lucide:github',
  // Direction
  'chevron-down': 'lucide:chevron-down',
  'chevron-right': 'lucide:chevron-right',
  'arrow-right': 'lucide:arrow-right',
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
