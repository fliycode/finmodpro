<script setup>
import RiskSummary from '../../components/RiskSummary.vue';
</script>

<template>
  <section class="workspace-risk">
    <RiskSummary />
  </section>
</template>

<style scoped>
.workspace-risk {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
</style>
