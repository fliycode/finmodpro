<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';

import ProfileIdentitySheet from '../../components/workspace/support/ProfileIdentitySheet.vue';
import { authStorage } from '../../lib/auth-storage.js';
import { isAdminProfile } from '../../lib/session-state.js';

const profile = computed(() => authStorage.getProfile());
const user = computed(() => profile.value?.user || {});
const displayName = computed(() => user.value.username || '当前用户');
const email = computed(() => user.value.email || '未设置邮箱');
const initials = computed(() => displayName.value.trim().slice(0, 1).toUpperCase() || 'U');
const roleLabel = computed(() => (isAdminProfile(profile.value) ? '管理员' : '用户'));
const groupsLabel = computed(() => {
  const groups = profile.value?.groups || [];
  return groups.length > 0 ? groups.join(' / ') : '未分配角色组';
});
const permissionsLabel = computed(() => {
  const permissions = profile.value?.permissions || [];
  return permissions.length > 0 ? `${permissions.length} 项权限` : '暂无显式权限';
});
</script>

<template>
  <section class="workspace-support-page">
    <header class="workspace-support-page__header">
      <div>
        <p class="workspace-support-page__eyebrow">Support surface</p>
        <h1>个人信息</h1>
      </div>
    </header>

    <ProfileIdentitySheet>
      <template #identity>
        <section class="profile-panel">
          <div class="profile-panel__avatar">{{ initials }}</div>
          <div class="profile-panel__identity">
            <span>{{ roleLabel }}</span>
            <h2>{{ displayName }}</h2>
            <p>{{ email }}</p>
          </div>
          <div class="profile-panel__actions">
            <RouterLink v-if="isAdminProfile(profile)" to="/admin/overview">进入管理台</RouterLink>
            <RouterLink to="/workspace/qa">返回问答</RouterLink>
          </div>
        </section>
      </template>

      <template #access>
        <section class="profile-details">
          <div class="profile-detail">
            <span>用户名</span>
            <strong>{{ displayName }}</strong>
          </div>
          <div class="profile-detail">
            <span>邮箱</span>
            <strong>{{ email }}</strong>
          </div>
          <div class="profile-detail">
            <span>角色组</span>
            <strong>{{ groupsLabel }}</strong>
          </div>
          <div class="profile-detail">
            <span>权限</span>
            <strong>{{ permissionsLabel }}</strong>
          </div>
        </section>
      </template>
    </ProfileIdentitySheet>
  </section>
</template>

<style scoped>
.workspace-support-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.workspace-support-page__eyebrow {
  margin: 0 0 6px;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #8b7358;
}

.workspace-support-page h1 {
  margin: 0;
  color: #2f2418;
  font-size: 34px;
  line-height: 1.06;
  letter-spacing: -0.03em;
}

.profile-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
}

.profile-panel__avatar {
  width: 72px;
  height: 72px;
  border-radius: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #7f5b2f;
  color: #fbf6ed;
  font-size: 28px;
  font-weight: 800;
}

.profile-panel__identity {
  min-width: 0;
}

.profile-panel__identity span {
  display: inline-flex;
  margin-bottom: 6px;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(154, 106, 44, 0.12);
  color: #8b5f2d;
  font-size: 12px;
  font-weight: 700;
}

.profile-panel__identity h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  color: #2f2418;
}

.profile-panel__identity p {
  margin: 6px 0 0;
  color: #6f5a42;
}

.profile-panel__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.profile-panel__actions a {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 12px;
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 10px;
  background: rgba(255, 251, 245, 0.96);
  color: #2f2418;
  font-weight: 700;
  text-decoration: none;
}

.profile-details {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.profile-detail {
  min-width: 0;
  padding: 18px 20px;
  border-bottom: 1px solid rgba(95, 69, 35, 0.12);
}

.profile-detail:nth-child(odd) {
  border-right: 1px solid rgba(95, 69, 35, 0.12);
}

.profile-detail span {
  display: block;
  margin-bottom: 5px;
  color: #8b7358;
  font-size: 12px;
  font-weight: 700;
}

.profile-detail strong {
  display: block;
  overflow-wrap: anywhere;
  color: #2f2418;
  font-size: 15px;
}

@media (max-width: 720px) {
  .profile-panel {
    grid-template-columns: 1fr;
  }

  .profile-panel__actions {
    justify-content: flex-start;
  }

  .profile-details {
    grid-template-columns: 1fr;
  }

  .profile-detail:nth-child(odd) {
    border-right: 0;
  }
}
</style>
