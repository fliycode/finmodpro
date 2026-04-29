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
  border: 1px solid rgba(96, 126, 255, 0.16);
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(13, 22, 38, 0.9), rgba(10, 17, 31, 0.92)),
    radial-gradient(circle at top right, rgba(90, 106, 255, 0.12), transparent 38%);
  box-shadow: 0 24px 58px -42px rgba(4, 10, 22, 0.96);
}

.profile-identity-sheet__hero {
  padding: 22px;
}

.profile-identity-sheet__access {
  padding: 0;
  overflow: hidden;
}
</style>
