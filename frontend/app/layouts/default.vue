<template>
  <div class="shell">
    <a
      class="shell__skip"
      href="#main"
    >К содержимому</a>
    <header class="shell__bar">
      <NuxtLink
        class="shell__brand"
        to="/"
      >Keitaro Wrapper</NuxtLink>
      <nav
        class="shell__nav"
        aria-label="Разделы"
      >
        <NuxtLink to="/">Кампании</NuxtLink>
        <NuxtLink to="/create">Создать</NuxtLink>
      </nav>
      <UiThemeToggle />
    </header>
    <main
      id="main"
      class="shell__main"
    >
      <slot />
    </main>
  </div>
</template>

<style scoped>
.shell {
  max-width: var(--page-max);
  margin: 0 auto;
  padding: 0 var(--page-pad) var(--gap-4);
}

.shell__skip {
  position: absolute;
  left: -9999px;
}

.shell__skip:focus {
  left: var(--page-pad);
  top: var(--gap-1);
  z-index: 20;
  padding: 8px 12px;
  border-radius: var(--r-box);
  background: var(--ground);
}

.shell__bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-1) var(--gap-3);
  padding: var(--gap-2) 0;
  border-bottom: 1px solid var(--hair);
}

.shell__brand {
  color: var(--ink);
  font-weight: 700;
  text-decoration: none;
}

.shell__nav {
  display: flex;
  flex: 1;
  gap: var(--gap-2);
}

.shell__nav a {
  display: inline-flex;
  align-items: center;
  min-height: var(--control);
  color: var(--cap);
  font-weight: 600;
  text-decoration: none;
}

.shell__nav a.router-link-exact-active {
  color: var(--ink);
  box-shadow: inset 0 -2px 0 var(--acc-line);
}

.shell__main {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-3);
  padding-top: var(--gap-3);
}
</style>
