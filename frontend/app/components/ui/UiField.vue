<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  modelValue: string
  /** A part of the value the user cannot change, shown inside the field (R-UX-01). */
  prefix?: string
  error?: string
  hint?: string
  placeholder?: string
  inputmode?: 'text' | 'numeric'
  required?: boolean
  disabled?: boolean
}>(), { inputmode: 'text' })

defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <div />
</template>
