<script setup lang="ts" generic="T extends string | number">
export interface ComboOption<Id> {
  id: Id
  name: string
}

defineProps<{
  label: string
  options: ComboOption<T>[]
  modelValue: ComboOption<T> | null
  placeholder?: string
  error?: string
  hint?: string
  /** Options are searched by the server: typing emits `search` instead of filtering here. */
  remote?: boolean
  loading?: boolean
  /** Options that are listed but cannot be chosen, with the reason shown next to them. */
  disabledIds?: T[]
  disabledNote?: string
  /** Show the identifier next to the name. */
  showId?: boolean
  /** When set, text that matches no option is offered as a new item. */
  createLabel?: (text: string) => string
}>()

defineEmits<{
  'update:modelValue': [ComboOption<T> | null]
  'search': [string]
  'create': [string]
}>()
</script>

<template>
  <div />
</template>
