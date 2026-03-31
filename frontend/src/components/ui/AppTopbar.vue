<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import { authStorage } from '../../lib/auth-storage.js';

const props = defineProps({
  title: {
    type: String,
    default: 'FinModPro',
  },
  switchTarget: {
    type: String,
    default: '',
  },
  switchLabel: {
    type: String,
    default: '',
  },
});

const profile = computed(() => authStorage.getProfile());
</script>

<template>
  <header class="app-topbar">
    <div>
      <p class="app-topbar__eyebrow">FinModPro</p>
      <h2>{{ props.title }}</h2>
    </div>

    <div class="app-topbar__actions">
      <span class="app-topbar__user">{{ profile.user.username || '当前用户' }}</span>
      <RouterLink v-if="props.switchTarget" :to="props.switchTarget">{{ props.switchLabel }}</RouterLink>
    </div>
  </header>
</template>
