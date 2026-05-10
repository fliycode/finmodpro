<script setup>
import { computed } from 'vue';

const props = defineProps({
  src: {
    type: String,
    default: '',
  },
  name: {
    type: String,
    default: '',
  },
  size: {
    type: String,
    default: 'md',
    validator: (v) => ['xs', 'sm', 'md', 'lg', 'xl'].includes(v),
  },
});

const initial = computed(() => {
  const n = (props.name || '').trim();
  return n ? n.slice(0, 1).toUpperCase() : 'U';
});

const sizeClass = computed(() => `app-avatar--${props.size}`);
</script>

<template>
  <span :class="['app-avatar', sizeClass]">
    <img
      v-if="props.src"
      :src="props.src"
      :alt="props.name || '头像'"
      class="app-avatar__img"
      @error="$event.target.style.display = 'none'"
    />
    <span v-if="!props.src" class="app-avatar__initial">{{ initial }}</span>
  </span>
</template>

<style scoped>
.app-avatar {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: var(--avatar-radius, 24px);
  background: linear-gradient(135deg, #315fff, #725dff);
  overflow: hidden;
}

.app-avatar__img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.app-avatar__initial {
  color: #f5f9ff;
  font-weight: 800;
  user-select: none;
}

/* Sizes */
.app-avatar--xs {
  width: 28px;
  height: 28px;
  --avatar-radius: 10px;
}

.app-avatar--xs .app-avatar__initial {
  font-size: 13px;
}

.app-avatar--sm {
  width: 36px;
  height: 36px;
  --avatar-radius: 12px;
}

.app-avatar--sm .app-avatar__initial {
  font-size: 15px;
}

.app-avatar--md {
  width: 44px;
  height: 44px;
  --avatar-radius: 14px;
}

.app-avatar--md .app-avatar__initial {
  font-size: 18px;
}

.app-avatar--lg {
  width: 64px;
  height: 64px;
  --avatar-radius: 20px;
}

.app-avatar--lg .app-avatar__initial {
  font-size: 26px;
}

.app-avatar--xl {
  width: 88px;
  height: 88px;
  --avatar-radius: 28px;
}

.app-avatar--xl .app-avatar__initial {
  font-size: 34px;
}
</style>
