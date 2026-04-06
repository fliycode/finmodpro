<script setup>
import finmodproMark from '../assets/finmodpro-mark.svg';
import finmodproWordmark from '../assets/finmodpro-wordmark.svg';

const capabilityItems = ['财务建模', '知识搜索', '风险决策'];

const trustMetrics = ['统一入口', '角色化工作台', '智能分析'];
</script>

<template>
  <div class="auth-layout">
    <section class="auth-layout__brand">
      <div class="auth-layout__brand-shell">
        <div class="auth-layout__brand-top">
          <div class="auth-layout__brand-lockup">
            <img class="auth-layout__brand-mark" :src="finmodproMark" alt="FinModPro" />
            <img class="auth-layout__wordmark" :src="finmodproWordmark" alt="FinModPro" />
          </div>
          <div>
            <p class="auth-layout__eyebrow">金融建模平台</p>
            <h1 class="auth-layout__headline">从数据到洞察，辅助更稳的财务与风险决策</h1>
          </div>
        </div>

        <div class="auth-layout__metrics" aria-label="平台特性">
          <span v-for="metric in trustMetrics" :key="metric" class="auth-layout__metric-chip">
            {{ metric }}
          </span>
        </div>

        <div class="auth-layout__capabilities">
          <article v-for="item in capabilityItems" :key="item" class="auth-layout__capability-card">
            <h2 class="auth-layout__capability-title">{{ item }}</h2>
          </article>
        </div>
      </div>
    </section>

    <main class="auth-layout__panel">
      <RouterView />
    </main>
  </div>
</template>
