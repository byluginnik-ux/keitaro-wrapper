<script setup lang="ts">
import type { CreatorOptions, FieldRemark, Option } from '../../../shared/types/api'

export interface CampaignDraft {
  name: string
  country: string
  offerId: number
  groupId: number
  trafficSourceId: number
  domainId?: number
  newDomainName?: string
}

defineProps<{
  options: CreatorOptions
  offers: Option<number>[]
  offersLoading?: boolean
  busy?: boolean
  /** Remarks of the server, each about one field of the input (R-UX-03). */
  remarks?: FieldRemark[]
  /** A refusal that is about no particular field, such as a tracker failure. */
  failure?: string | null
}>()

defineEmits<{
  'submit': [CampaignDraft]
  'search-offers': [string]
}>()
</script>

<template>
  <form />
</template>
