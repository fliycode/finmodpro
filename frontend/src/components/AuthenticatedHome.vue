<script setup>
import finmodproLogo from '../assets/finmodpro-logo.svg';

const props = defineProps({
  currentUser: {
    type: Object,
    required: true
  },
  isAdmin: {
    type: Boolean,
    required: true
  }
});

const emit = defineEmits(['navigate-admin', 'logout', 'enter-workbench']);

const highlights = [
  {
    title: '统一财务建模中台',
    description: '将建模、问答、风险摘要与模型配置串成同一条分析链路。'
  },
  {
    title: '可审计的权限边界',
    description: '基于角色组与权限标签控制后台、工作台与敏感操作访问。'
  },
  {
    title: '面向决策的交付速度',
    description: '把知识库、问答和运营看板放进同一个高频工作入口。'
  }
];

const metrics = [
  { label: '角色权限已加载', value: props.currentUser.permissions?.length ?? 0 },
  { label: '角色组', value: props.currentUser.groups?.length ?? 0 },
  { label: '可进入模块', value: props.isAdmin ? 3 : 2 }
];
</script>

<template>
  <section class="auth-shell auth-shell--logged-in">
    <div class="auth-backdrop"></div>
    <div class="auth-layout auth-layout--single">
      <aside class="brand-panel">
        <div class="brand-panel__eyebrow">Authenticated session</div>
        <div class="brand-lockup">
          <img :src="finmodproLogo" alt="FinModPro logo" class="brand-lockup__logo" />
          <div>
            <h1>FinModPro</h1>
            <p>企业级财务建模与智能分析工作入口</p>
          </div>
        </div>

        <div class="brand-story">
          <span class="brand-story__badge">已登录</span>
          <h2>欢迎回来，{{ currentUser.user.username }}</h2>
          <p>
            您的账号权限已同步完成，可继续进入工作台处理知识问答、风险摘要与模型配置。
          </p>
        </div>

        <div class="metric-grid">
          <article v-for="metric in metrics" :key="metric.label" class="metric-card">
            <span>{{ metric.label }}</span>
            <strong>{{ metric.value }}</strong>
          </article>
        </div>

        <div class="permission-panel">
          <div class="permission-panel__header">
            <h3>当前访问概况</h3>
            <span>{{ currentUser.groups.join(' / ') || '未分配角色' }}</span>
          </div>
          <div class="permission-tags">
            <span v-for="permission in currentUser.permissions" :key="permission" class="permission-tag">
              {{ permission }}
            </span>
            <span v-if="!currentUser.permissions.length" class="permission-tag permission-tag--muted">
              暂无权限标签
            </span>
          </div>
        </div>
      </aside>

      <section class="form-panel form-panel--logged-in">
        <div class="form-panel__content">
          <div class="panel-intro">
            <span class="panel-intro__eyebrow">Next destination</span>
            <h2>继续您的工作流</h2>
            <p>保留原有登录 / 注册 / 工作台 / 管理后台流程，仅升级入口层级与品牌体验。</p>
          </div>

          <div class="action-stack action-stack--single">
            <button type="button" class="primary-button" @click="emit('enter-workbench')">
              进入工作台
            </button>
            <button
              v-if="isAdmin"
              type="button"
              class="secondary-button"
              @click="emit('navigate-admin')"
            >
              打开管理后台
            </button>
            <button v-else type="button" class="secondary-button secondary-button--muted" disabled>
              管理后台仅对管理员开放
            </button>
            <button type="button" class="ghost-button" @click="emit('logout')">
              切换账号
            </button>
          </div>

          <div class="highlights-panel">
            <article v-for="item in highlights" :key="item.title" class="highlight-card">
              <div class="highlight-card__icon"></div>
              <div>
                <h3>{{ item.title }}</h3>
                <p>{{ item.description }}</p>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
