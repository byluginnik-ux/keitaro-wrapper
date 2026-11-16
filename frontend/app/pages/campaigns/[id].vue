<script setup lang="ts">
import type { StreamCommand } from '../../components/editor/StreamCard.vue'
import { api, toApiError } from '../../composables/api'
import type { ApiRequest } from '../../composables/api'
import type { EditorScreen, Option, StreamView } from '../../../shared/types/api'

const route = useRoute()
const campaignId = String(route.params.id)

const { data: screen, error: loadError, status, refresh } = await useAsyncData(
  `editor-${campaignId}`,
  () => api<EditorScreen>(`/api/campaigns/${campaignId}/editor`),
)

useHead({ title: () => `${screen.value?.campaign.name ?? 'Кампания'} — Keitaro Wrapper` })

const pending = ref<Record<string, StreamCommand['action']>>({})
const errors = ref<Record<string, string>>({})
const found = ref<Record<string, Option<number>[]>>({})
const searching = ref<Record<string, boolean>>({})
const syncing = ref(false)
const syncError = ref<string | null>(null)
const lastSearch: Record<string, number> = {}

function request(streamId: string, command: StreamCommand): [string, ApiRequest] {
  const stream = `/api/streams/${streamId}`
  switch (command.action) {
    case 'add': return [`${stream}/offers`, { method: 'POST', body: { offerId: command.offerId } }]
    case 'remove': return [`${stream}/offers/${command.offerId}`, { method: 'DELETE' }]
    case 'restore': return [`${stream}/offers/${command.offerId}/restore`, { method: 'POST' }]
    case 'pin': return [`${stream}/offers/${command.offerId}/pin`, { method: 'PUT', body: { share: command.share } }]
    case 'unpin': return [`${stream}/offers/${command.offerId}/pin`, { method: 'DELETE' }]
    case 'cancel': return [`${stream}/cancel`, { method: 'POST' }]
    case 'push': return [`${stream}/push`, { method: 'POST' }]
  }
}

/** Every action answers with the whole stream; the page shows what the server said (R-UX-16). */
async function run(streamId: string, command: StreamCommand) {
  if (pending.value[streamId] || !screen.value) return
  pending.value = { ...pending.value, [streamId]: command.action }
  const { [streamId]: _old, ...otherErrors } = errors.value
  errors.value = otherErrors
  syncError.value = null
  try {
    const [url, options] = request(streamId, command)
    const updated = await api<StreamView>(url, options)
    screen.value = {
      ...screen.value,
      streams: screen.value.streams.map(stream => (stream.id === streamId ? updated : stream)),
    }
  }
  catch (error) {
    errors.value = { ...errors.value, [streamId]: toApiError(error).message }
  }
  finally {
    const { [streamId]: _done, ...rest } = pending.value
    pending.value = rest
  }
}

async function searchOffers(streamId: string, search: string) {
  const mine = lastSearch[streamId] = (lastSearch[streamId] ?? 0) + 1
  searching.value = { ...searching.value, [streamId]: true }
  let offers: Option<number>[] = []
  try {
    offers = await api<Option<number>[]>('/api/offers', { query: { search } })
  }
  catch {
    offers = []
  }
  if (mine !== lastSearch[streamId]) return
  found.value = { ...found.value, [streamId]: offers }
  searching.value = { ...searching.value, [streamId]: false }
}

async function sync() {
  if (!screen.value || syncing.value) return
  syncing.value = true
  syncError.value = null
  try {
    screen.value = await api<EditorScreen>('/api/campaigns/fetch', {
      method: 'POST',
      body: { keitaroId: screen.value.campaign.keitaroId },
    })
    errors.value = {}
  }
  catch (error) {
    syncError.value = toApiError(error).message
  }
  finally {
    syncing.value = false
  }
}

onMounted(() => screen.value?.streams.filter(stream => stream.acceptsOffers).forEach(stream => searchOffers(stream.id, '')))
</script>

<template>
  <section class="page">
    <p
      v-if="status === 'pending'"
      role="status"
    >
      Загрузка кампании…
    </p>
    <UiNotice
      v-else-if="loadError || !screen"
      tone="risk"
      title="Кампания не открылась"
    >
      <p>{{ toApiError(loadError).message }}</p>
      <div class="page__row">
        <UiButton @click="refresh()">
          Повторить
        </UiButton>
        <NuxtLink to="/">К списку кампаний</NuxtLink>
      </div>
    </UiNotice>
    <template v-else>
      <header class="page__head">
        <div>
          <h1>{{ screen.campaign.name }}</h1>
          <p class="small data">
            ID в Keitaro: {{ screen.campaign.keitaroId }}<template v-if="screen.campaign.country">
              · страна {{ screen.campaign.country }}
            </template>
          </p>
        </div>
        <div class="page__row">
          <a
            :href="screen.campaign.trackerLink"
            target="_blank"
            rel="noopener"
          >Открыть в Keitaro<span class="visually-hidden"> (в новой вкладке)</span></a>
          <UiButton
            :busy="syncing"
            @click="sync"
          >
            Обновить из Keitaro
          </UiButton>
        </div>
      </header>

      <UiNotice
        v-if="syncError"
        tone="risk"
        title="Кампания не обновлена"
      >
        {{ syncError }}
      </UiNotice>

      <UiNotice
        v-if="!screen.streams.length"
        title="В кампании нет потоков"
      >
        Создайте потоки в Keitaro и нажмите «Обновить из Keitaro».
      </UiNotice>
      <EditorStreamCard
        v-for="stream in screen.streams"
        :key="stream.id"
        :stream="stream"
        :offers="found[stream.id] ?? []"
        :offers-loading="searching[stream.id]"
        :pending="pending[stream.id] ?? null"
        :error="errors[stream.id] ?? null"
        @command="run(stream.id, $event)"
        @search-offers="searchOffers(stream.id, $event)"
      />
    </template>
  </section>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-3);
}

.page__head {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--gap-2);
}

.page__row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-1) var(--gap-2);
}
</style>
