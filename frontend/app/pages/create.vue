<script setup lang="ts">
import type { CampaignDraft } from '../components/creator/CreatorForm.vue'
import { api, toApiError } from '../composables/api'
import { followTask } from '../composables/publication'
import { stepLabel } from '../composables/task-labels'
import type { CampaignView, CreatorOptions, EditorScreen, FieldRemark, Option, TaskView } from '../../shared/types/api'

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
/** The task that is creating the campaign, as far as it has gone (R-UX-06). */
const progress = ref<TaskView | null>(null)
/** The task ID lives until the request is answered, so a resend is the same task (R-TK-04). */
let taskId: string | null = null

async function submit(draft: CampaignDraft) {
  busy.value = true
  failure.value = null
  remarks.value = []
  progress.value = null
  try {
    taskId ??= crypto.randomUUID()
    const queued = await api<TaskView>('/api/campaigns', { method: 'POST', body: { ...draft, taskId } })
    taskId = null
    progress.value = queued
    const task = queued.finished
      ? queued
      : await followTask(queued.id, {
          load: id => api<TaskView>(`/api/tasks/${id}`),
          onUpdate: (seen) => { progress.value = seen },
        })
    if (!task) failure.value = 'Создание ещё выполняется. Итог появится на странице «Задачи».'
    else if (task.status !== 'succeeded' || !task.campaignId) failure.value = task.refusal ?? 'Кампания не создана'
    else created.value = (await api<EditorScreen>(`/api/campaigns/${task.campaignId}/editor`)).campaign
  }
  catch (error) {
    const refusal = toApiError(error)
    // the request was answered: the next attempt is a new task
    if (refusal.code !== 'network') taskId = null
    remarks.value = refusal.fields ?? []
    // a remark about a field is shown at the field; the rest goes above the form (R-UX-03)
    failure.value = refusal.code === 'validation_failed' && remarks.value.length ? null : refusal.message
  }
  finally {
    busy.value = false
    progress.value = null
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
    <template v-else>
      <p
        v-if="busy"
        class="progress"
        role="status"
      >
        Создаётся…<template v-if="progress?.steps.length">
          {{ stepLabel(progress.steps[progress.steps.length - 1]!.name) }}
        </template>
      </p>
      <CreatorForm
        :options="options"
        :offers="offers"
        :offers-loading="offersLoading"
        :busy="busy"
        :remarks="remarks"
        :failure="failure"
        @search-offers="searchOffers"
        @submit="submit"
      />
    </template>
  </section>
</template>

<style scoped>
.progress {
  margin: 0;
}

.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-3);
}
</style>
