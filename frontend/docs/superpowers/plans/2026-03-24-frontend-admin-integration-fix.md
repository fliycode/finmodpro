# FinModPro Frontend Admin Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the frontend admin dashboard with the backend API contract for user group management.

**Architecture:** Update API service layer and Vue component to handle user groups as an array of strings (names) instead of an array of objects.

**Tech Stack:** Vue 3 (Composition API), Vite

---

### Task 1: Update API Service Layer

**Files:**
- Modify: `src/api/admin.js`

- [ ] **Step 1: Update `updateUserGroups` parameter and payload**
Change `groupIds` to `groupNames` and ensure it sends the correct payload.

```javascript
// src/api/admin.js
// ...
    updateUserGroups(userId, groupNames) {
      return putJson(config, `/api/admin/users/${userId}/groups`, {
        groups: groupNames
      });
    }
// ...
```

---

### Task 2: Update AdminUsers Component Logic

**Files:**
- Modify: `src/components/AdminUsers.vue`

- [ ] **Step 1: Fix `filteredUsers` computed property**
Update it to handle `user.groups` as `string[]`.

```javascript
const filteredUsers = computed(() => {
  return users.value.filter(user => {
    const usernameMatch = user.username.toLowerCase().includes(searchQuery.value.toLowerCase());
    const emailMatch = user.email.toLowerCase().includes(searchQuery.value.toLowerCase());
    const matchesSearch = usernameMatch || emailMatch;
    
    // Fix: user.groups is now string[]
    const matchesGroup = !filterGroup.value || user.groups.includes(filterGroup.value);
    return matchesSearch && matchesGroup;
  });
});
```

- [ ] **Step 2: Update `handleUpdateGroups`**
Map selected groups to names and update local state with string array.

```javascript
const handleUpdateGroups = async () => {
  if (!selectedUser.value) return;
  isUpdating.value = true;
  try {
    // selectedUser.value.groups is now string[]
    const groupNames = [...selectedUser.value.groups];
    await adminApi.updateUserGroups(selectedUser.value.id, groupNames);
    
    // Local refresh: find and update user in the list
    const index = users.value.findIndex(u => u.id === selectedUser.value.id);
    if (index !== -1) {
      users.value[index].groups = groupNames;
    }
    
    closeEditDrawer();
  } catch (err) {
    alert(err.message || '更新失败');
  } finally {
    isUpdating.value = false;
  }
};
```

- [ ] **Step 3: Update `toggleGroupSelection` and `isGroupSelected`**
Modify these to work with group names.

```javascript
const toggleGroupSelection = (groupName) => {
  const index = selectedUser.value.groups.indexOf(groupName);
  if (index === -1) {
    selectedUser.value.groups.push(groupName);
  } else {
    selectedUser.value.groups.splice(index, 1);
  }
};

const isGroupSelected = (groupName) => {
  return selectedUser.value && selectedUser.value.groups.includes(groupName);
};
```

---

### Task 3: Update AdminUsers Template

**Files:**
- Modify: `src/components/AdminUsers.vue`

- [ ] **Step 1: Update user table group display**
Iterate over string array.

```html
<div class="group-tags">
  <span v-for="groupName in user.groups" :key="groupName" class="group-tag">{{ groupName }}</span>
  <span v-if="!user.groups.length" class="no-groups">无角色</span>
</div>
```

- [ ] **Step 2: Update edit drawer group selection**
Pass `g.name` instead of `g.id`.

```html
<div 
  v-for="g in groups" 
  :key="g.id" 
  class="group-item" 
  :class="{ selected: isGroupSelected(g.name) }"
  @click="toggleGroupSelection(g.name)"
>
  <div class="checkbox">{{ isGroupSelected(g.name) ? '✓' : '' }}</div>
  <div class="group-info">
    <span class="group-name">{{ g.name }}</span>
  </div>
</div>
```

---

### Task 4: Verification and Build

- [ ] **Step 1: Run build to ensure no regressions**
Run: `npm run build`
Expected: Successful build.

- [ ] **Step 2: Final Report**
Summarize changes and results.
