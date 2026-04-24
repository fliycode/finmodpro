<script setup>
const props = defineProps({
  name: {
    type: String,
    required: true,
  },
});

const iconPaths = {
  spark: [
    'M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9L12 3Z',
  ],
  database: [
    'M12 4c-4.4 0-8 1.3-8 3s3.6 3 8 3 8-1.3 8-3-3.6-3-8-3Z',
    'M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
    'M4 17c0 1.7 3.6 3 8 3s8-1.3 8-3',
    'M4 7v10',
    'M20 7v10',
  ],
  history: [
    'M4 12a8 8 0 1 0 2.3-5.6',
    'M4 4v4h4',
    'M12 8v4l2.5 2.5',
  ],
  shield: [
    'M12 3 5 6v5c0 4.1 2.8 7.9 7 9 4.2-1.1 7-4.9 7-9V6l-7-3Z',
    'm9.5 12 1.7 1.7 3.3-3.4',
  ],
  dashboard: [
    'M4 13h7V4H4v9Z',
    'M13 20h7v-7h-7v7Z',
    'M13 11h7V4h-7v7Z',
    'M4 20h7v-5H4v5Z',
  ],
  users: [
    'M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2',
    'M9.5 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
    'M20 21v-2a4 4 0 0 0-3-3.9',
    'M15 3.1a4 4 0 0 1 0 7.8',
  ],
  sliders: [
    'M4 21v-7',
    'M4 10V3',
    'M12 21v-9',
    'M12 5V3',
    'M20 21v-4',
    'M20 10V3',
    'M2 10h4',
    'M10 12h4',
    'M18 10h4',
    'M2 14h4',
    'M10 5h4',
    'M18 17h4',
  ],
  beaker: [
    'M9 3h6',
    'M10 3v6.4l-5.5 8.8A2 2 0 0 0 6.2 21h11.6a2 2 0 0 0 1.7-2.8L14 9.4V3',
    'M8.5 14h7',
  ],
  eye: [
    'M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z',
    'M12 15.2a3.2 3.2 0 1 0 0-6.4 3.2 3.2 0 0 0 0 6.4Z',
  ],
  'eye-off': [
    'm3 3 18 18',
    'M10.7 5.2A10.7 10.7 0 0 1 12 5c6 0 9.5 7 9.5 7a18.6 18.6 0 0 1-4 4.8',
    'M6.2 6.2C3.8 8 2.5 12 2.5 12s3.5 7 9.5 7c1.8 0 3.3-.4 4.6-1',
    'M9.9 9.9a3.2 3.2 0 0 0 4.2 4.2',
  ],
  send: [
    'M22 2 11 13',
    'M22 2 15 22 11 13 2 9 22 2Z',
  ],
  moon: [
    'M21 12.8A8.7 8.7 0 0 1 11.2 3 7 7 0 1 0 21 12.8Z',
  ],
  sun: [
    'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
    'M12 2v2',
    'M12 20v2',
    'm4.95-16.95-1.4 1.4',
    'm8.45 17.55-1.4 1.4',
    'M22 12h-2',
    'M4 12H2',
    'm19.95 7.05-1.4-1.4',
    'm5.45 5.45-1.4-1.4',
  ],
};
</script>

<template>
  <svg
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    :aria-label="props.name"
    role="img"
  >
    <path v-for="path in iconPaths[props.name] ?? []" :key="path" :d="path" />
  </svg>
</template>
