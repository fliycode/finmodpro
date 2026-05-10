<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
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

const stats = reactive({
  question_count: 0,
  question_count_today: 0,
  document_count: 0,
  usage_days: 0,
});
const dateJoined = ref('');

const loading = ref(true);

const fetchProfile = async () => {
  loading.value = true;
  try {
    const data = await authApi.me();
    authStorage.saveProfile(data);
    if (data.stats) {
      Object.assign(stats, data.stats);
    }
    dateJoined.value = data.date_joined || '';
  } catch {
    // silent
  } finally {
    loading.value = false;
  }
};

onMounted(fetchProfile);

// ── avatar upload ─────────────────────────────────────────────────────
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
    const u = updatedProfile?.user || updatedProfile;
    if (u?.avatar_url) {
      u.avatar_url = u.avatar_url.split('?')[0] + '?t=' + Date.now();
    }
    authStorage.saveProfile(updatedProfile);
  } catch (error) {
    uploadError.value = error.message || '上传失败，请重试';
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = '';
  }
};

// ── edit account ──────────────────────────────────────────────────────
const editingField = ref(null);
const editValue = ref('');
const editSaving = ref(false);
const editError = ref('');

const startEdit = (field) => {
  editError.value = '';
  editingField.value = field;
  editValue.value = field === 'username' ? user.value.username : user.value.email;
};

const cancelEdit = () => {
  editingField.value = null;
  editValue.value = '';
};

const saveEdit = async () => {
  if (!editingField.value) return;
  editSaving.value = true;
  editError.value = '';
  try {
    const payload = {
      username: editingField.value === 'username' ? editValue.value.trim() : user.value.username,
      email: editingField.value === 'email' ? editValue.value.trim() : user.value.email,
    };
    const updated = await authApi.updateProfile(payload);
    authStorage.saveProfile(updated);
    editingField.value = null;
  } catch (error) {
    editError.value = error.message || '保存失败';
  } finally {
    editSaving.value = false;
  }
};

// ── change password ───────────────────────────────────────────────────
const showPasswordForm = ref(false);
const passwordForm = reactive({ oldPassword: '', newPassword: '', confirmPassword: '' });
const passwordSaving = ref(false);
const passwordError = ref('');
const passwordSuccess = ref('');

const togglePasswordForm = () => {
  showPasswordForm.value = !showPasswordForm.value;
  passwordError.value = '';
  passwordSuccess.value = '';
  passwordForm.oldPassword = '';
  passwordForm.newPassword = '';
  passwordForm.confirmPassword = '';
};

const savePassword = async () => {
  passwordError.value = '';
  passwordSuccess.value = '';

  if (!passwordForm.oldPassword || !passwordForm.newPassword) {
    passwordError.value = '请填写旧密码和新密码';
    return;
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    passwordError.value = '两次输入的新密码不一致';
    return;
  }

  passwordSaving.value = true;
  try {
    await authApi.changePassword({
      oldPassword: passwordForm.oldPassword,
      newPassword: passwordForm.newPassword,
    });
    passwordSuccess.value = '密码已修改';
    showPasswordForm.value = false;
    passwordForm.oldPassword = '';
    passwordForm.newPassword = '';
    passwordForm.confirmPassword = '';
  } catch (error) {
    passwordError.value = error.message || '修改失败';
  } finally {
    passwordSaving.value = false;
  }
};

const formatDate = (iso) => {
  if (!iso) return '—';
  return iso.split('T')[0];
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

      <template #stats>
        <div class="stat-card">
          <div class="stat-card__value">{{ stats.question_count }}</div>
          <div class="stat-card__label">提问次数</div>
          <div class="stat-card__sub">今日 {{ stats.question_count_today }}</div>
        </div>
        <div class="stat-card">
          <div class="stat-card__value">{{ stats.document_count }}</div>
          <div class="stat-card__label">上传文档</div>
        </div>
        <div class="stat-card">
          <div class="stat-card__value">{{ stats.usage_days }}</div>
          <div class="stat-card__label">使用天数</div>
        </div>
      </template>

      <template #account>
        <section class="profile-details">
          <div class="profile-detail">
            <span>用户名</span>
            <div v-if="editingField === 'username'" class="profile-detail__edit">
              <input v-model="editValue" class="profile-detail__input" @keyup.enter="saveEdit" />
              <div class="profile-detail__edit-actions">
                <button :disabled="editSaving" @click="saveEdit">{{ editSaving ? '保存中...' : '保存' }}</button>
                <button @click="cancelEdit">取消</button>
              </div>
              <p v-if="editError" class="profile-panel__error">{{ editError }}</p>
            </div>
            <div v-else class="profile-detail__row">
              <strong>{{ displayName }}</strong>
              <button class="profile-detail__edit-btn" @click="startEdit('username')">编辑</button>
            </div>
          </div>
          <div class="profile-detail">
            <span>邮箱</span>
            <div v-if="editingField === 'email'" class="profile-detail__edit">
              <input v-model="editValue" class="profile-detail__input" @keyup.enter="saveEdit" />
              <div class="profile-detail__edit-actions">
                <button :disabled="editSaving" @click="saveEdit">{{ editSaving ? '保存中...' : '保存' }}</button>
                <button @click="cancelEdit">取消</button>
              </div>
              <p v-if="editError" class="profile-panel__error">{{ editError }}</p>
            </div>
            <div v-else class="profile-detail__row">
              <strong>{{ email }}</strong>
              <button class="profile-detail__edit-btn" @click="startEdit('email')">编辑</button>
            </div>
          </div>
          <div class="profile-detail">
            <span>注册时间</span>
            <strong>{{ formatDate(dateJoined) }}</strong>
          </div>
        </section>
      </template>

      <template #security>
        <section class="security-section">
          <div class="security-section__header">
            <span class="security-section__label">密码</span>
            <button class="profile-detail__edit-btn" @click="togglePasswordForm">
              {{ showPasswordForm ? '取消' : '修改密码' }}
            </button>
          </div>
          <p v-if="passwordSuccess" class="security-section__success">{{ passwordSuccess }}</p>
          <div v-if="showPasswordForm" class="password-form">
            <div class="password-form__field">
              <label>旧密码</label>
              <input v-model="passwordForm.oldPassword" type="password" autocomplete="current-password" />
            </div>
            <div class="password-form__field">
              <label>新密码</label>
              <input v-model="passwordForm.newPassword" type="password" autocomplete="new-password" />
            </div>
            <div class="password-form__field">
              <label>确认新密码</label>
              <input v-model="passwordForm.confirmPassword" type="password" autocomplete="new-password" @keyup.enter="savePassword" />
            </div>
            <p v-if="passwordError" class="profile-panel__error">{{ passwordError }}</p>
            <button class="password-form__submit" :disabled="passwordSaving" @click="savePassword">
              {{ passwordSaving ? '保存中...' : '确认修改' }}
            </button>
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

/* ── identity panel ──────────────────────────────────────────────────── */

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

/* ── stat cards ──────────────────────────────────────────────────────── */

.stat-card {
  border: 1px solid var(--border, rgba(96, 126, 255, 0.16));
  border-radius: 16px;
  background: var(--surface-2);
  padding: 18px 20px;
  text-align: center;
}

html[data-theme='dark'] .stat-card {
  background:
    linear-gradient(180deg, rgba(13, 22, 38, 0.9), rgba(10, 17, 31, 0.92)),
    radial-gradient(circle at top right, rgba(90, 106, 255, 0.12), transparent 38%);
  border-color: rgba(96, 126, 255, 0.16);
}

.stat-card__value {
  font-size: 32px;
  font-weight: 700;
  line-height: 1.1;
  color: var(--text-primary);
}

.stat-card__label {
  margin-top: 4px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-muted);
}

.stat-card__sub {
  margin-top: 2px;
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.7;
}

/* ── account details ─────────────────────────────────────────────────── */

.profile-details {
  display: flex;
  flex-direction: column;
}

.profile-detail {
  min-width: 0;
  padding: 18px 20px;
  border-bottom: 1px solid var(--border);
}

.profile-detail:last-child {
  border-bottom: 0;
}

.profile-detail > span {
  display: block;
  margin-bottom: 5px;
  color: var(--text-muted);
  font-size: 12px;
  font-weight: 700;
}

.profile-detail__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.profile-detail__row strong {
  overflow-wrap: anywhere;
  color: var(--text-primary);
  font-size: 15px;
}

.profile-detail__edit-btn {
  flex-shrink: 0;
  padding: 4px 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.profile-detail__edit-btn:hover {
  background: var(--surface-2);
}

.profile-detail__edit {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.profile-detail__input {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

.profile-detail__input:focus {
  border-color: #2457c5;
}

.profile-detail__edit-actions {
  display: flex;
  gap: 8px;
}

.profile-detail__edit-actions button {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.profile-detail__edit-actions button:first-child {
  background: #2457c5;
  color: #fff;
  border-color: #2457c5;
}

.profile-detail__edit-actions button:first-child:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.profile-detail__edit-actions button:last-child {
  background: var(--surface-1);
  color: var(--text-primary);
}

/* ── security section ────────────────────────────────────────────────── */

.security-section {
  padding: 18px 20px;
}

.security-section__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.security-section__label {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.security-section__success {
  margin: 8px 0 0;
  color: #21815c;
  font-size: 13px;
}

.password-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-top: 16px;
}

.password-form__field {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.password-form__field label {
  font-size: 12px;
  font-weight: 700;
  color: var(--text-muted);
}

.password-form__field input {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface-1);
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

.password-form__field input:focus {
  border-color: #2457c5;
}

.password-form__submit {
  align-self: flex-start;
  padding: 8px 20px;
  border: none;
  border-radius: 8px;
  background: #2457c5;
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.password-form__submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
}
</style>
