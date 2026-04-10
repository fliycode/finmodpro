<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';

import FinancialQA from '../../components/FinancialQA.vue';

const route = useRoute();
const sessionId = computed(() => route.query.session ?? null);
</script>

<template>
  <div class="page-stack workspace-page">
    <FinancialQA :session-id="sessionId" />
  </div>
</template>
