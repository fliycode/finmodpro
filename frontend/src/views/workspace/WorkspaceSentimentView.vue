<script setup>
import SentimentAnalysis from '../../components/SentimentAnalysis.vue';
</script>

<template>
  <section class="workspace-dossier-page">
    <SentimentAnalysis />
  </section>
</template>

<style scoped>
.workspace-dossier-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

</style>
