<script setup>
import { RouterView } from 'vue-router';

import AppSidebar from '../components/ui/AppSidebar.vue';
import FlashStack from '../components/ui/FlashStack.vue';
import ThemeToggle from '../components/ui/ThemeToggle.vue';
</script>

<template>
  <div class="app-shell app-shell--workspace">
    <AppSidebar area="workspace" />
    <main class="workspace-frame">
      <header class="workspace-frame__utility">
        <div class="workspace-frame__utility-copy">
          <p class="workspace-frame__eyebrow">Dossier workspace</p>
          <strong>结论先行，证据随后，动作最后。</strong>
        </div>
        <ThemeToggle />
      </header>
      <FlashStack />
      <section class="workspace-frame__body">
        <RouterView />
      </section>
    </main>
  </div>
</template>
