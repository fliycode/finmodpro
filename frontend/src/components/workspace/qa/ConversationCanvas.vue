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
  border: 1px solid rgba(95, 123, 255, 0.18);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(12, 20, 36, 0.9), rgba(9, 15, 28, 0.9)),
    radial-gradient(circle at top, rgba(84, 99, 255, 0.14), transparent 42%);
  box-shadow: 0 22px 56px -36px rgba(3, 9, 22, 0.88);
  backdrop-filter: blur(18px);
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
  border-bottom: 1px solid rgba(95, 123, 255, 0.12);
}

.conversation-canvas__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7c93bb;
}

.conversation-canvas h2 {
  margin: 0;
  font-size: 22px;
  line-height: 1.2;
  color: #eef4ff;
}

.conversation-canvas__meta {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  border: 1px solid rgba(93, 130, 255, 0.2);
  background: rgba(49, 68, 130, 0.24);
  color: #a9beff;
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
