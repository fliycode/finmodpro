<script setup>
defineProps({
  active: {
    type: Boolean,
    default: true,
  },
  messageCount: {
    type: Number,
    default: 0,
  },
});
</script>

<template>
  <section class="conversation-canvas" :class="{ 'is-active': active }">
    <header class="conversation-canvas__header">
      <div>
        <p class="conversation-canvas__eyebrow">Conversation region</p>
        <h2>AI 会话主屏</h2>
      </div>
      <span class="conversation-canvas__meta">{{ messageCount }} 条消息</span>
    </header>
    <div v-if="$slots.toolbar" class="conversation-canvas__toolbar">
      <slot name="toolbar" />
    </div>
    <div class="conversation-canvas__body">
      <slot />
    </div>
  </section>
</template>

<style scoped>
.conversation-canvas {
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--line-soft);
  border-radius: 16px;
  background: var(--surface-2);
  box-shadow: var(--shadow-md);
  overflow: hidden;
}

.conversation-canvas__header,
.conversation-canvas__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px 0;
}

.conversation-canvas__header {
  padding-bottom: 14px;
  border-bottom: 1px solid var(--line-soft);
}

.conversation-canvas__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.conversation-canvas h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
  color: var(--text-primary);
}

.conversation-canvas__meta {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid var(--line-soft);
  background: var(--brand-soft);
  color: var(--brand);
  font-size: 12px;
  font-weight: 700;
}

.conversation-canvas__toolbar {
  padding-top: 14px;
  padding-bottom: 16px;
}

.conversation-canvas__body {
  flex: 1;
  min-height: 0;
}

@media (max-width: 1024px) {
  .conversation-canvas {
    display: none;
  }

  .conversation-canvas.is-active {
    display: flex;
  }
}
</style>
