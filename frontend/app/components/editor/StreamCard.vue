<script setup lang="ts">
import type { Option, StreamView } from '../../../shared/types/api'

export type StreamCommand
  = | { action: 'add', offerId: number }
    | { action: 'remove' | 'restore' | 'unpin', offerId: number }
    | { action: 'pin', offerId: number, share: number }
    | { action: 'cancel' | 'push' }

defineProps<{
  stream: StreamView
  /** Offers found for the "add" list. */
  offers: Option<number>[]
  offersLoading?: boolean
  /** The action whose request is running, if any. */
  pending?: StreamCommand['action'] | null
  /** The last refusal; the draft stays as it was (R-UX-16). */
  error?: string | null
}>()

defineEmits<{
  'command': [StreamCommand]
  'search-offers': [string]
}>()
</script>

<template>
  <section />
</template>
