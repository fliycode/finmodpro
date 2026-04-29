<template>
  <section class="profile-identity-sheet">
    <header class="profile-identity-sheet__hero">
      <slot name="identity" />
    </header>
    <section class="profile-identity-sheet__access">
      <slot name="access" />
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
.profile-identity-sheet__access {
  border: 1px solid rgba(95, 69, 35, 0.14);
  border-radius: 22px;
  background: rgba(251, 246, 237, 0.94);
  box-shadow: 0 18px 52px -42px rgba(80, 54, 20, 0.28);
}

.profile-identity-sheet__hero {
  padding: 22px;
}

.profile-identity-sheet__access {
  padding: 0;
  overflow: hidden;
}
</style>
