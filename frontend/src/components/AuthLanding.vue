<script setup>
import finmodproLogo from '../assets/finmodpro-logo.svg';

const props = defineProps({
  activeTab: {
    type: String,
    required: true
  },
  showPassword: {
    type: Boolean,
    required: true
  },
  isLoading: {
    type: Boolean,
    required: true
  },
  status: {
    type: Object,
    required: true
  },
  formData: {
    type: Object,
    required: true
  },
  errors: {
    type: Object,
    required: true
  }
});

const emit = defineEmits([
  'toggle-tab',
  'submit',
  'toggle-password'
]);

const capabilityPills = [
  'Financial Modeling',
  'Risk Intelligence',
  'Governed Access'
];

const signalMetrics = [
  { label: 'Workflow', value: 'Modeling + QA' },
  { label: 'Control', value: 'RBAC Ready' },
  { label: 'Output', value: 'Decision-ready' }
];
</script>

<template>
  <section class="auth-lobby">
    <div class="auth-lobby__noise"></div>
    <div class="auth-lobby__ambient auth-lobby__ambient--one"></div>
    <div class="auth-lobby__ambient auth-lobby__ambient--two"></div>

    <div class="auth-lobby__frame">
      <aside class="brand-stage">
        <p class="brand-stage__eyebrow">Financial Modeling Platform</p>

        <div class="brand-stage__lockup">
          <div class="brand-stage__logo-ring">
            <img :src="finmodproLogo" alt="FinModPro logo" class="brand-stage__logo" />
          </div>
          <div>
            <h1>FinModPro</h1>
            <p class="brand-stage__lede">进入更可信的财务建模与风险决策工作流。</p>
          </div>
        </div>

        <div class="brand-stage__story">
          <span class="brand-stage__badge">Brand Lobby</span>
          <h2>为建模、分析、治理与协作准备的统一入口</h2>
          <p>
            一个兼顾展示感与登录效率的品牌门厅，让 FinModPro 在首屏就建立信任、
            辨识度与专业气质。
          </p>
        </div>

        <div class="brand-stage__pills" aria-label="Platform capabilities">
          <span v-for="pill in capabilityPills" :key="pill">{{ pill }}</span>
        </div>

        <div class="brand-stage__metrics">
          <article v-for="item in signalMetrics" :key="item.label" class="brand-stage__metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
      </aside>

      <section class="form-chamber">
        <div class="form-chamber__inner">
          <div class="tabs" role="tablist" aria-label="Authentication tabs">
            <button
              type="button"
              class="tab-btn"
              :class="{ active: activeTab === 'login' }"
              :disabled="isLoading"
              @click="emit('toggle-tab', 'login')"
            >
              登录
            </button>
            <button
              type="button"
              class="tab-btn"
              :class="{ active: activeTab === 'register' }"
              :disabled="isLoading"
              @click="emit('toggle-tab', 'register')"
            >
              注册
            </button>
          </div>

          <div class="panel-intro">
            <span class="panel-intro__eyebrow">
              {{ activeTab === 'login' ? 'Welcome back' : 'Create workspace access' }}
            </span>
            <h2>{{ activeTab === 'login' ? '登录后继续您的建模与分析工作' : '创建 FinModPro 账号以启用团队工作流' }}</h2>
            <p>
              {{
                activeTab === 'login'
                  ? '输入账户信息后即可继续访问统一的建模、问答与风控工作空间。'
                  : '完成注册后即可登录并进入统一的财务建模、问答与治理体验。'
              }}
            </p>
          </div>

          <div v-if="status.message" :class="['status-box', status.type]" role="status" aria-live="polite">
            {{ status.message }}
          </div>

          <form class="auth-form" novalidate @submit="emit('submit', $event)">
            <div class="form-group">
              <label for="username">用户名</label>
              <input
                id="username"
                v-model="formData.username"
                type="text"
                :placeholder="activeTab === 'register' ? '例如：finance.ops' : '请输入用户名'"
                :class="{ 'input-error': errors.username }"
                :disabled="isLoading"
              />
              <span v-if="errors.username" class="error-msg">{{ errors.username }}</span>
            </div>

            <div v-if="activeTab === 'register'" class="form-group">
              <label for="email">电子邮箱</label>
              <input
                id="email"
                v-model="formData.email"
                type="email"
                placeholder="name@company.com"
                :class="{ 'input-error': errors.email }"
                :disabled="isLoading"
              />
              <span v-if="errors.email" class="error-msg">{{ errors.email }}</span>
            </div>

            <div class="form-group">
              <div class="label-row">
                <label for="password">密码</label>
                <a v-if="activeTab === 'login'" href="#" class="inline-link">忘记密码？</a>
              </div>
              <div class="password-input-wrapper">
                <input
                  id="password"
                  v-model="formData.password"
                  :type="showPassword ? 'text' : 'password'"
                  placeholder="••••••••"
                  :class="{ 'input-error': errors.password }"
                  :disabled="isLoading"
                />
                <button
                  type="button"
                  class="toggle-pwd"
                  :disabled="isLoading"
                  @click="emit('toggle-password')"
                >
                  {{ showPassword ? '隐藏' : '显示' }}
                </button>
              </div>
              <span v-if="errors.password" class="error-msg">{{ errors.password }}</span>
            </div>

            <div v-if="activeTab === 'register'" class="form-group">
              <label for="confirmPassword">确认密码</label>
              <input
                id="confirmPassword"
                v-model="formData.confirmPassword"
                :type="showPassword ? 'text' : 'password'"
                placeholder="再次输入密码"
                :class="{ 'input-error': errors.confirmPassword }"
                :disabled="isLoading"
              />
              <span v-if="errors.confirmPassword" class="error-msg">{{ errors.confirmPassword }}</span>
            </div>

            <div v-if="activeTab === 'register'" class="form-group checkbox-group">
              <label class="checkbox-label" for="agreeTerms">
                <input id="agreeTerms" v-model="formData.agreeTerms" type="checkbox" :disabled="isLoading" />
                <span>我同意 <a href="#" class="inline-link">服务条款</a> 与 <a href="#" class="inline-link">隐私政策</a></span>
              </label>
              <span v-if="errors.agreeTerms" class="error-msg">{{ errors.agreeTerms }}</span>
            </div>

            <button type="submit" class="primary-button" :disabled="isLoading">
              <span v-if="isLoading" class="loader"></span>
              <span v-else>{{ activeTab === 'login' ? '登录 FinModPro' : '创建账号并继续' }}</span>
            </button>
          </form>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.auth-lobby {
  --lobby-bg: #f5efe6;
  --lobby-bg-deep: #eadcca;
  --lobby-panel: rgba(255, 252, 247, 0.76);
  --lobby-panel-strong: rgba(255, 249, 241, 0.92);
  --lobby-border: rgba(83, 58, 27, 0.12);
  --lobby-ink: #221912;
  --lobby-muted: #705c49;
  --lobby-accent: #a77b46;
  --lobby-accent-soft: rgba(167, 123, 70, 0.14);
  min-height: 100vh;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
  background:
    radial-gradient(circle at top left, rgba(224, 199, 160, 0.64), transparent 30%),
    radial-gradient(circle at 85% 18%, rgba(198, 170, 130, 0.28), transparent 22%),
    linear-gradient(135deg, #f7f1e8 0%, #efe4d4 52%, #faf5ee 100%);
}

.auth-lobby__noise,
.auth-lobby__ambient {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.auth-lobby__noise {
  opacity: 0.18;
  background-image:
    linear-gradient(rgba(95, 71, 39, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(95, 71, 39, 0.025) 1px, transparent 1px);
  background-size: 28px 28px;
  mask-image: radial-gradient(circle at center, black 45%, transparent 88%);
}

.auth-lobby__ambient {
  filter: blur(28px);
  opacity: 0.7;
  animation: ambientDrift 14s ease-in-out infinite;
}

.auth-lobby__ambient--one {
  inset: auto auto 10% 6%;
  width: 420px;
  height: 420px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(218, 190, 145, 0.48) 0%, rgba(218, 190, 145, 0) 68%);
}

.auth-lobby__ambient--two {
  inset: 8% 4% auto auto;
  width: 360px;
  height: 360px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(176, 146, 104, 0.22) 0%, rgba(176, 146, 104, 0) 70%);
  animation-delay: -5s;
}

.auth-lobby__frame {
  position: relative;
  z-index: 1;
  width: min(1160px, 100%);
  min-height: 720px;
  display: grid;
  grid-template-columns: minmax(0, 1.08fr) minmax(360px, 0.92fr);
  border: 1px solid var(--lobby-border);
  border-radius: 34px;
  background: linear-gradient(135deg, rgba(255, 253, 249, 0.82), rgba(247, 239, 228, 0.68));
  box-shadow:
    0 32px 80px rgba(93, 67, 38, 0.12),
    inset 0 1px 0 rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(18px);
  overflow: hidden;
  animation: lobbyReveal 720ms cubic-bezier(0.2, 0.8, 0.2, 1) both;
}

.brand-stage {
  position: relative;
  padding: 56px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 28px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), rgba(255, 255, 255, 0)),
    linear-gradient(145deg, rgba(248, 241, 232, 0.88), rgba(239, 226, 205, 0.8));
}

.brand-stage::after {
  content: '';
  position: absolute;
  inset: 20px;
  border: 1px solid rgba(91, 67, 39, 0.08);
  border-radius: 26px;
  pointer-events: none;
}

.brand-stage__eyebrow,
.panel-intro__eyebrow {
  margin: 0;
  color: var(--lobby-accent);
  letter-spacing: 0.24em;
  text-transform: uppercase;
  font-size: 0.73rem;
  font-weight: 600;
}

.brand-stage__lockup,
.brand-stage__story,
.brand-stage__pills,
.brand-stage__metrics,
.form-chamber__inner {
  opacity: 0;
  animation: elementReveal 540ms ease both;
}

.brand-stage__lockup {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 20px;
  align-items: center;
  animation-delay: 120ms;
}

.brand-stage__logo-ring {
  position: relative;
  width: 112px;
  height: 112px;
  border-radius: 32px;
  display: grid;
  place-items: center;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.92), rgba(233, 214, 183, 0.92));
  box-shadow:
    0 18px 40px rgba(94, 70, 38, 0.16),
    inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.brand-stage__logo-ring::before {
  content: '';
  position: absolute;
  inset: -10px;
  border-radius: 38px;
  border: 1px solid rgba(170, 134, 86, 0.18);
}

.brand-stage__logo {
  width: 74px;
  height: 74px;
  object-fit: contain;
  animation: lobbyFloat 8s ease-in-out infinite;
}

.brand-stage h1,
.brand-stage h2,
.form-chamber h2 {
  margin: 0;
  color: var(--lobby-ink);
  font-family: Georgia, 'Times New Roman', 'Noto Serif SC', serif;
}

.brand-stage h1 {
  font-size: clamp(3.2rem, 5vw, 5rem);
  line-height: 0.95;
  letter-spacing: -0.04em;
}

.brand-stage__lede {
  margin: 10px 0 0;
  max-width: 440px;
  color: var(--lobby-muted);
  font-size: 1.02rem;
  line-height: 1.7;
}

.brand-stage__story {
  display: flex;
  flex-direction: column;
  gap: 14px;
  max-width: 520px;
  animation-delay: 220ms;
}

.brand-stage__badge {
  width: fit-content;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255, 252, 247, 0.74);
  border: 1px solid rgba(167, 123, 70, 0.14);
  color: var(--lobby-accent);
  font-size: 0.8rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-stage h2 {
  font-size: clamp(2rem, 3vw, 3rem);
  line-height: 1.05;
  letter-spacing: -0.035em;
}

.brand-stage__story p,
.panel-intro p {
  margin: 0;
  color: var(--lobby-muted);
  line-height: 1.75;
  font-size: 0.98rem;
}

.brand-stage__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  animation-delay: 320ms;
}

.brand-stage__pills span {
  padding: 10px 16px;
  border-radius: 999px;
  background: rgba(255, 252, 247, 0.66);
  border: 1px solid rgba(95, 71, 39, 0.1);
  color: #483628;
  font-size: 0.92rem;
}

.brand-stage__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  animation-delay: 420ms;
}

.brand-stage__metric {
  padding: 18px 18px 20px;
  border-radius: 20px;
  border: 1px solid rgba(95, 71, 39, 0.08);
  background: rgba(255, 252, 247, 0.58);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
}

.brand-stage__metric span {
  display: block;
  color: #8b6e4c;
  font-size: 0.78rem;
  letter-spacing: 0.15em;
  text-transform: uppercase;
}

.brand-stage__metric strong {
  display: block;
  margin-top: 10px;
  color: var(--lobby-ink);
  font-size: 1rem;
}

.form-chamber {
  padding: 24px;
  display: flex;
  align-items: stretch;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.48), rgba(255, 255, 255, 0.14)),
    rgba(255, 248, 238, 0.4);
}

.form-chamber__inner {
  width: 100%;
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 24px;
  border-radius: 28px;
  border: 1px solid rgba(95, 71, 39, 0.1);
  background: var(--lobby-panel-strong);
  box-shadow:
    0 18px 42px rgba(99, 73, 42, 0.08),
    inset 0 1px 0 rgba(255, 255, 255, 0.82);
  animation-delay: 280ms;
}

.tabs {
  display: inline-grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
  padding: 8px;
  border-radius: 999px;
  background: rgba(111, 87, 58, 0.08);
  align-self: flex-start;
}

.tab-btn {
  border: 0;
  border-radius: 999px;
  padding: 10px 18px;
  background: transparent;
  color: var(--lobby-muted);
  font-size: 0.95rem;
  cursor: pointer;
  transition: transform 180ms ease, background-color 180ms ease, color 180ms ease, box-shadow 180ms ease;
}

.tab-btn.active {
  background: #251a13;
  color: #fff7ef;
  box-shadow: 0 10px 18px rgba(37, 26, 19, 0.16);
}

.tab-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  color: var(--lobby-ink);
}

.panel-intro {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.form-chamber h2 {
  font-size: clamp(1.75rem, 2vw, 2.35rem);
  line-height: 1.1;
  letter-spacing: -0.03em;
}

.status-box {
  padding: 14px 16px;
  border-radius: 18px;
  font-size: 0.94rem;
  line-height: 1.55;
  animation: statusFade 220ms ease;
}

.status-box.success {
  background: rgba(96, 148, 92, 0.12);
  color: #305d2d;
  border: 1px solid rgba(96, 148, 92, 0.18);
}

.status-box.error {
  background: rgba(168, 77, 62, 0.1);
  color: #8d3429;
  border: 1px solid rgba(168, 77, 62, 0.18);
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 9px;
}

.form-group label,
.label-row {
  color: var(--lobby-ink);
  font-size: 0.92rem;
  font-weight: 600;
}

.label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-group input {
  width: 100%;
  border: 1px solid rgba(95, 71, 39, 0.14);
  border-radius: 18px;
  padding: 15px 18px;
  background: rgba(255, 255, 255, 0.82);
  color: var(--lobby-ink);
  outline: none;
  transition:
    border-color 180ms ease,
    box-shadow 180ms ease,
    background-color 180ms ease,
    transform 180ms ease;
}

.form-group input::placeholder {
  color: rgba(112, 92, 73, 0.72);
}

.form-group input:focus {
  border-color: rgba(167, 123, 70, 0.48);
  background: #fffdf9;
  box-shadow: 0 0 0 4px rgba(167, 123, 70, 0.12);
  transform: translateY(-1px);
}

.input-error {
  border-color: rgba(168, 77, 62, 0.38) !important;
  box-shadow: 0 0 0 4px rgba(168, 77, 62, 0.1) !important;
}

.password-input-wrapper {
  position: relative;
}

.password-input-wrapper input {
  padding-right: 76px;
}

.toggle-pwd {
  position: absolute;
  top: 50%;
  right: 12px;
  transform: translateY(-50%);
  border: 0;
  background: transparent;
  color: var(--lobby-accent);
  cursor: pointer;
  font-size: 0.86rem;
  font-weight: 600;
}

.checkbox-group {
  gap: 8px;
}

.checkbox-label {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  color: var(--lobby-muted);
  font-size: 0.92rem;
  line-height: 1.6;
  font-weight: 400;
}

.checkbox-label input {
  width: 18px;
  height: 18px;
  margin-top: 3px;
  padding: 0;
}

.inline-link {
  color: var(--lobby-accent);
  text-decoration: none;
}

.inline-link:hover {
  text-decoration: underline;
}

.error-msg {
  color: #a24537;
  font-size: 0.84rem;
}

.primary-button {
  border: 0;
  border-radius: 18px;
  padding: 16px 22px;
  background: linear-gradient(135deg, #2d2119, #1b1510);
  color: #fff8f0;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
}

.primary-button:hover:not(:disabled) {
  transform: translateY(-2px);
  filter: brightness(1.03);
  box-shadow: 0 18px 26px rgba(35, 25, 18, 0.16);
}

.primary-button:disabled,
.tab-btn:disabled,
.toggle-pwd:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.loader {
  display: inline-block;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  border: 2px solid rgba(255, 248, 240, 0.4);
  border-top-color: #fff8f0;
  animation: spin 0.8s linear infinite;
}

@keyframes lobbyReveal {
  from {
    opacity: 0;
    transform: translateY(26px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes elementReveal {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes ambientDrift {
  0%, 100% {
    transform: translate3d(0, 0, 0) scale(1);
  }
  50% {
    transform: translate3d(10px, -18px, 0) scale(1.06);
  }
}

@keyframes lobbyFloat {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-8px);
  }
}

@keyframes statusFade {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 1080px) {
  .auth-lobby {
    padding: 20px;
  }

  .auth-lobby__frame {
    grid-template-columns: 1fr;
    min-height: auto;
  }

  .brand-stage,
  .form-chamber__inner {
    padding: 32px;
  }

  .brand-stage__metrics {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .auth-lobby {
    padding: 12px;
  }

  .brand-stage,
  .form-chamber {
    padding: 18px;
  }

  .brand-stage,
  .form-chamber__inner {
    gap: 22px;
    padding: 24px;
  }

  .brand-stage__lockup {
    grid-template-columns: 1fr;
  }

  .brand-stage__logo-ring {
    width: 88px;
    height: 88px;
    border-radius: 26px;
  }

  .brand-stage__logo {
    width: 58px;
    height: 58px;
  }

  .tabs {
    width: 100%;
  }

  .tab-btn {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .auth-lobby__frame,
  .auth-lobby__ambient,
  .brand-stage__logo,
  .brand-stage__lockup,
  .brand-stage__story,
  .brand-stage__pills,
  .brand-stage__metrics,
  .form-chamber__inner,
  .status-box,
  .loader {
    animation: none !important;
    transition: none !important;
  }

  .form-group input:focus,
  .tab-btn:hover:not(:disabled),
  .primary-button:hover:not(:disabled) {
    transform: none;
  }
}
</style>
