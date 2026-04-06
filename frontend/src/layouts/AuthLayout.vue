<script setup>
import finmodproMark from '../assets/finmodpro-mark.svg';
</script>

<template>
  <div class="auth-layout">
    <section class="auth-layout__brand">
      <div class="auth-layout__brand-shell">
        <div class="auth-layout__brand-top">
          <div class="auth-layout__brand-lockup">
            <img class="auth-layout__brand-mark" :src="finmodproMark" alt="FinModPro" />
            <div class="auth-layout__brand-text">
              <span class="auth-layout__brand-name">FinModPro</span>
              <span class="auth-layout__brand-subname">金融建模平台</span>
            </div>
          </div>
          <div>
            <h1 class="auth-layout__headline">从数据到洞察，辅助更稳的财务与风险决策</h1>
          </div>
        </div>
      </div>
    </section>

    <main class="auth-layout__panel">
      <RouterView />
    </main>
  </div>
</template>
