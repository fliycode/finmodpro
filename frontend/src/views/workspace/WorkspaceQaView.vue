<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import FinancialQA from '../../components/FinancialQA.vue';

const route = useRoute();
const sessionId = computed(() => route.query.session ?? null);
</script>

<template>
  <section class="workspace-qa">
    <FinancialQA :session-id="sessionId" />
  </section>
</template>

<style scoped>
.workspace-qa {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
</style>
