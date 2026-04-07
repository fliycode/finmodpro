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

<style scoped>
.auth-layout {
  min-height: 100svh;
  display: grid;
  grid-template-columns: minmax(360px, 1fr) minmax(420px, 0.92fr);
  background: var(--page-bg);
}

.auth-layout__brand {
  display: flex;
  align-items: center;
  padding: 72px 64px;
  border-right: 1px solid var(--line-soft);
  background: var(--surface-1);
  color: var(--text-primary);
}

.auth-layout__brand-shell {
  display: flex;
  flex-direction: column;
  gap: 24px;
  max-width: 560px;
}

.auth-layout__brand-top {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.auth-layout__brand-lockup {
  display: flex;
  align-items: center;
  gap: 16px;
}

.auth-layout__brand-mark {
  width: 52px;
  height: 52px;
  border-radius: 16px;
  flex-shrink: 0;
}

.auth-layout__headline {
  margin: 0;
  max-width: 640px;
  font-size: 56px;
  line-height: 1.08;
  letter-spacing: -0.04em;
  font-weight: 700;
  color: var(--text-primary);
}

.auth-layout__brand-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.auth-layout__brand-name {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--text-primary);
  text-transform: uppercase;
}

.auth-layout__brand-subname {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-muted);
  letter-spacing: 0.12em;
}

.auth-layout__panel {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
}

@media (max-width: 960px) {
  .auth-layout {
    grid-template-columns: 1fr;
  }

  .auth-layout__brand {
    padding: 48px 24px 24px;
    border-right: 0;
    border-bottom: 1px solid var(--line-soft);
  }

  .auth-layout__brand-lockup {
    gap: 12px;
  }

  .auth-layout__brand-name {
    font-size: 22px;
  }

  .auth-layout__headline {
    font-size: 42px;
    line-height: 1.08;
  }

  .auth-layout__panel {
    padding: 24px;
  }
}
</style>
