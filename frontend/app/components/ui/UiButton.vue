<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'danger' | 'quiet'
  size?: 'md' | 'lg'
  type?: 'button' | 'submit'
  disabled?: boolean
  /** A request started by this button is running. */
  busy?: boolean
}>(), { variant: 'secondary', size: 'md', type: 'button' })
</script>

<template>
  <button
    class="button"
    :class="[`button--${variant}`, `button--${size}`]"
    :type="type"
    :disabled="disabled || busy"
    :aria-busy="busy || undefined"
  >
    <span
      v-if="busy"
      class="button__busy"
      aria-hidden="true"
    >…</span>
    <slot />
  </button>
</template>

<style scoped>
.button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--gap-1);
  min-height: var(--control);
  padding: 0 var(--gap-2);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--ink);
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--ease), border-color var(--ease), color var(--ease);
}

.button--lg {
  min-height: var(--control-lg);
  padding: 0 var(--gap-3);
}

.button:hover:not(:disabled) {
  background: var(--tint);
}

.button--primary {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--ground);
}

.button--primary:hover:not(:disabled) {
  background: var(--cap);
  border-color: var(--cap);
}

.button--danger {
  border-color: var(--risk-deep);
  color: var(--risk-text);
}

.button--quiet {
  border-color: transparent;
  color: var(--acc-text);
}

.button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.button__busy {
  font-family: var(--mono);
}
</style>
