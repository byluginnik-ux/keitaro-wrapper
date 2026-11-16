<script setup lang="ts">
import type { OfferView } from '../../../shared/types/api'

defineProps<{
  offer: OfferView
  /** A request of the stream is running: nothing can be pressed. */
  locked?: boolean
}>()

defineEmits<{
  pin: [share: number]
  unpin: []
  remove: []
  restore: []
}>()
</script>

<template>
  <li />
</template>
