<script setup>
import { computed, ref } from 'vue';
import { RouterLink } from 'vue-router';

import AppAvatar from '../../components/ui/AppAvatar.vue';
import ProfileIdentitySheet from '../../components/workspace/support/ProfileIdentitySheet.vue';
import { authApi } from '../../api/auth.js';
import { authStorage } from '../../lib/auth-storage.js';
import { isAdminProfile } from '../../lib/session-state.js';

const profile = computed(() => authStorage.getProfile());
const user = computed(() => profile.value?.user || {});
const displayName = computed(() => user.value.username || '当前用户');
const email = computed(() => user.value.email || '未设置邮箱');
const avatarUrl = computed(() => user.value.avatar_url || '');
const roleLabel = computed(() => (isAdminProfile(profile.value) ? '管理员' : '用户'));
const groupsLabel = computed(() => {
  const groups = profile.value?.groups || [];
  return groups.length > 0 ? groups.join(' / ') : '未分配角色组';
});
const permissionsLabel = computed(() => {
  const permissions = profile.value?.permissions || [];
  return permissions.length > 0 ? `${permissions.length} 项权限` : '暂无显式权限';
});

const fileInput = ref(null);
const uploading = ref(false);
const uploadError = ref('');

const openFilePicker = () => {
  uploadError.value = '';
  fileInput.value?.click();
};

const handleFileChange = async (event) => {
  const file = event.target.files?.[0];
  if (!file) return;

  if (file.size > 2 * 1024 * 1024) {
    uploadError.value = '头像文件不能超过 2MB';
    return;
  }

  uploading.value = true;
  uploadError.value = '';
  try {
    const updatedProfile = await authApi.uploadAvatar(file);
    // Cache-bust: Nginx caches /media/ for 7 days, so append timestamp to force re-fetch
    const user = updatedProfile?.user || updatedProfile;
    if (user?.avatar_url) {
      user.avatar_url = user.avatar_url.split('?')[0] + '?t=' + Date.now();
    }
    authStorage.saveProfile(updatedProfile);
  } catch (error) {
    uploadError.value = error.message || '上传失败，请重试';
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = '';
  }
};
</script>

<template>
  <section class="workspace-support-page">
    <ProfileIdentitySheet>
      <template #identity>
        <section class="profile-panel">
          <button
            type="button"
            class="profile-panel__avatar-btn"
            :aria-label="avatarUrl ? '更换头像' : '上传头像'"
            @click="openFilePicker"
          >
            <AppAvatar :src="avatarUrl" :name="displayName" size="xl" />
            <span class="profile-panel__avatar-overlay">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/>
                <circle cx="12" cy="13" r="4"/>
              </svg>
            </span>
            <span v-if="uploading" class="profile-panel__avatar-loading">上传中...</span>
          </button>
          <input
            ref="fileInput"
            type="file"
            accept="image/jpeg,image/png,image/gif,image/webp"
            class="profile-panel__file-input"
            @change="handleFileChange"
          />

          <div class="profile-panel__identity">
            <span>{{ roleLabel }}</span>
            <h2>{{ displayName }}</h2>
            <p>{{ email }}</p>
            <p v-if="uploadError" class="profile-panel__error">{{ uploadError }}</p>
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

.profile-panel {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 18px;
}

.profile-panel__avatar-btn {
  position: relative;
  display: inline-flex;
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  border-radius: 28px;
  overflow: hidden;
}

.profile-panel__avatar-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.45);
  color: #fff;
  opacity: 0;
  transition: opacity 0.2s ease-out;
  border-radius: inherit;
}

.profile-panel__avatar-btn:hover .profile-panel__avatar-overlay {
  opacity: 1;
}

.profile-panel__avatar-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  border-radius: inherit;
}

.profile-panel__file-input {
  display: none;
}

.profile-panel__identity {
  min-width: 0;
}

.profile-panel__identity span {
  display: inline-flex;
  margin-bottom: 6px;
  padding: 3px 9px;
  border-radius: 999px;
  background: rgba(59, 115, 255, 0.1);
  color: #4a6fa5;
  font-size: 12px;
  font-weight: 700;
}

html[data-theme='dark'] .profile-panel__identity span {
  background: rgba(59, 115, 255, 0.16);
  color: #9db5ff;
}

.profile-panel__identity h2 {
  margin: 0;
  font-size: 26px;
  line-height: 1.2;
  color: var(--text-primary);
}

.profile-panel__identity p {
  margin: 6px 0 0;
  color: var(--text-muted);
}

.profile-panel__error {
  color: #ff8a8a !important;
  font-size: 13px;
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
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface-1);
  color: var(--text-primary);
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
  border-bottom: 1px solid var(--border);
}

.profile-detail:nth-child(odd) {
  border-right: 1px solid var(--border);
}

.profile-detail span {
  display: block;
  margin-bottom: 5px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.profile-detail strong {
  display: block;
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-size: 15px;
}

@media (max-width: 720px) {
  .profile-panel {
    grid-template-columns: 1fr;
  }

  .profile-panel__avatar-btn {
    justify-self: start;
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
