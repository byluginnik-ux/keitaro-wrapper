<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'risk' | 'accent' | 'muted'
  title?: string
}>(), { tone: 'muted' })
</script>

<template>
  <div />
</template>
