<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'risk' | 'accent' | 'muted'
  title?: string
}>(), { tone: 'muted' })
</script>

<template>
  <div
    class="notice"
    :class="`notice--${tone}`"
    :role="tone === 'risk' ? 'alert' : 'status'"
  >
    <p
      v-if="title"
      class="notice__title"
    >
      {{ title }}
    </p>
    <slot />
  </div>
</template>

<style scoped>
.notice {
  display: grid;
  gap: var(--gap-1);
  padding: var(--gap-2);
  border: 1px solid var(--hair);
  border-left: 4px solid var(--line);
  border-radius: var(--r-box);
  background: var(--mist);
}

.notice--risk {
  border-left-color: var(--risk-deep);
}

.notice--accent {
  border-left-color: var(--acc-line);
}

.notice__title {
  font-weight: 600;
}

.notice--risk .notice__title {
  color: var(--risk-text);
}
</style>
