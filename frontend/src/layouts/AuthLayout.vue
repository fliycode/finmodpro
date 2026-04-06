<script setup>
import finmodproLogo from '../assets/finmodpro-logo.svg';

const capabilityItems = [
  {
    title: '财务建模',
    description: '多维指标分析、结构化测算与模型推演。',
  },
  {
    title: '知识检索',
    description: '文档入库、语义召回与问答辅助一体化。',
  },
  {
    title: '风险决策',
    description: '风险识别、过程跟踪与报告输出闭环。',
  },
];

const trustMetrics = [
  '统一认证入口',
  '角色化工作台',
  '面向财务与风控场景',
];
</script>

<template>
  <div class="auth-layout">
    <section class="auth-layout__brand">
      <div class="auth-layout__brand-shell">
        <div class="auth-layout__brand-top">
          <img class="auth-layout__logo" :src="finmodproLogo" alt="FinModPro" />
          <div>
            <p class="auth-layout__eyebrow">FINANCIAL MODELING PLATFORM</p>
            <h1>从财务数据到风险洞察，一站式完成建模、检索与决策支持。</h1>
            <p class="auth-layout__subtitle">
              FinModPro 面向财务分析、知识管理与风控场景，提供统一工作台、智能问答与结构化决策辅助能力。
            </p>
          </div>
        </div>

        <div class="auth-layout__metrics" aria-label="平台特性">
          <span v-for="metric in trustMetrics" :key="metric" class="auth-layout__metric-chip">
            {{ metric }}
          </span>
        </div>

        <div class="auth-layout__capabilities">
          <article v-for="item in capabilityItems" :key="item.title" class="auth-layout__capability-card">
            <div class="auth-layout__capability-dot" />
            <div>
              <h2 class="auth-layout__capability-title">{{ item.title }}</h2>
              <p class="auth-layout__capability-desc">{{ item.description }}</p>
            </div>
          </article>
        </div>
      </div>
    </section>

    <main class="auth-layout__panel">
      <RouterView />
    </main>
  </div>
</template>
