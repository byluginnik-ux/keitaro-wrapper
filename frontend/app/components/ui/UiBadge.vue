<script setup lang="ts">
withDefaults(defineProps<{
  /** accent — changed or chosen; muted — inactive; risk — refusal. */
  tone?: 'accent' | 'muted' | 'risk'
}>(), { tone: 'muted' })
</script>

<template>
  <div />
</template>
