<template>
  <section class="profile-identity-sheet">
    <header class="profile-identity-sheet__hero">
      <slot name="identity" />
    </header>
    <section v-if="$slots.stats" class="profile-identity-sheet__stats">
      <slot name="stats" />
    </section>
    <section class="profile-identity-sheet__access">
      <slot name="account" />
    </section>
    <section v-if="$slots.security" class="profile-identity-sheet__security">
      <slot name="security" />
    </section>
  </section>
</template>

<style scoped>
.profile-identity-sheet {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-width: 920px;
  width: 100%;
  margin: 0 auto;
}

.profile-identity-sheet__hero,
.profile-identity-sheet__access,
.profile-identity-sheet__security {
  border: 1px solid var(--border, rgba(96, 126, 255, 0.16));
  border-radius: 16px;
  overflow: hidden;
}

.profile-identity-sheet__hero {
  padding: 22px;
}

.profile-identity-sheet__stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.profile-identity-sheet__access,
.profile-identity-sheet__security {
  padding: 0;
  overflow: hidden;
}

@media (max-width: 600px) {
  .profile-identity-sheet__stats {
    grid-template-columns: 1fr;
  }
}
</style>
