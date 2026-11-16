<script setup lang="ts">
withDefaults(defineProps<{
  /** accent — changed or chosen; muted — inactive; risk — refusal. */
  tone?: 'accent' | 'muted' | 'risk'
}>(), { tone: 'muted' })
</script>

<template>
  <span
    class="badge"
    :class="`badge--${tone}`"
  ><slot /></span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  color: var(--cap);
  font: 700 0.6875rem / 0.75rem var(--mono);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  white-space: nowrap;
}

.badge--accent {
  border-color: var(--acc);
  background: var(--acc);
  color: var(--ink);
}

.badge--risk {
  border-color: var(--risk);
  background: var(--risk);
  color: var(--ink);
}
</style>
