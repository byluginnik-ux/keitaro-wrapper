<script setup lang="ts">
import type { CampaignDraft } from '../components/creator/CreatorForm.vue'
import { api, toApiError } from '../composables/api'
import type { CampaignView, CreatorOptions, FieldRemark, Option } from '../../shared/types/api'

useHead({ title: 'Новая кампания — Keitaro Wrapper' })

const { data: options, error: optionsError, status, refresh } = await useAsyncData('creator-options', () => api<CreatorOptions>('/api/creator/options'))

const offers = ref<Option<number>[]>([])
const offersLoading = ref(false)
let lastSearch = 0

async function searchOffers(search: string) {
  const mine = ++lastSearch
  offersLoading.value = true
  try {
    const found = await api<Option<number>[]>('/api/offers', { query: { search } })
    if (mine === lastSearch) offers.value = found
  }
  catch {
    if (mine === lastSearch) offers.value = []
  }
  finally {
    if (mine === lastSearch) offersLoading.value = false
  }
}
onMounted(() => searchOffers(''))

const busy = ref(false)
const remarks = ref<FieldRemark[]>([])
const failure = ref<string | null>(null)
const created = ref<CampaignView | null>(null)

async function submit(draft: CampaignDraft) {
  busy.value = true
  failure.value = null
  remarks.value = []
  try {
    created.value = await api<CampaignView>('/api/campaigns', { method: 'POST', body: draft })
  }
  catch (error) {
    const refusal = toApiError(error)
    remarks.value = refusal.fields ?? []
    // a remark about a field is shown at the field; the rest goes above the form (R-UX-03)
    failure.value = refusal.code === 'validation_failed' && remarks.value.length ? null : refusal.message
  }
  finally {
    busy.value = false
  }
}

async function again() {
  created.value = null
  await refresh()
}
</script>

<template>
  <section class="page">
    <header>
      <h1>Новая кампания</h1>
      <p class="small">
        Кампания с двумя потоками: первый уводит выбранную страну на google.com, второй ведёт на оффер.
      </p>
    </header>

    <CreatorResult
      v-if="created"
      :campaign="created"
      @again="again"
    />
    <p
      v-else-if="status === 'pending'"
      role="status"
    >
      Загрузка справочников…
    </p>
    <UiNotice
      v-else-if="optionsError || !options"
      tone="risk"
      title="Справочники не загрузились"
    >
      <p>{{ toApiError(optionsError).message }}</p>
      <div>
        <UiButton @click="refresh()">
          Повторить
        </UiButton>
      </div>
    </UiNotice>
    <CreatorForm
      v-else
      :options="options"
      :offers="offers"
      :offers-loading="offersLoading"
      :busy="busy"
      :remarks="remarks"
      :failure="failure"
      @search-offers="searchOffers"
      @submit="submit"
    />
  </section>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-3);
}
</style>
