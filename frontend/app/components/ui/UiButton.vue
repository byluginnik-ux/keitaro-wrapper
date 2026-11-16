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
  <div />
</template>
