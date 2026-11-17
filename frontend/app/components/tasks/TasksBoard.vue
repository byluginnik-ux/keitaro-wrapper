<script setup lang="ts">
import type { TaskStatus, TaskView, TasksScreen } from '../../../shared/types/api'

defineProps<{
  screen: TasksScreen
  /** The status the list is narrowed to; null — every task. */
  filter: TaskStatus | null
  /** Tasks whose request is running, by task ID. */
  pending?: Record<string, 'cancel' | 'retry'>
  /** The last refusal of an action, by task ID (R-UX-31). */
  errors?: Record<string, string>
}>()

defineEmits<{
  cancel: [TaskView]
  retry: [TaskView]
  filter: [TaskStatus | null]
}>()
</script>

<template>
  <div class="board" />
</template>
