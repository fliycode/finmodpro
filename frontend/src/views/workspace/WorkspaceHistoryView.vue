<script setup>
import { useRouter } from 'vue-router';

import ChatHistory from '../../components/ChatHistory.vue';

const router = useRouter();

const openSession = (sessionId) => {
  router.push({ path: '/workspace/qa', query: { session: sessionId } });
};
</script>

<template>
  <ChatHistory @open-session="openSession" />
</template>
