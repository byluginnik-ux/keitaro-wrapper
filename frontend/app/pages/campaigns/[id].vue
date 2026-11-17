<script setup lang="ts">
import type { StreamCommand } from '../../components/editor/StreamCard.vue'
import { api, toApiError } from '../../composables/api'
import type { ApiRequest } from '../../composables/api'
import { followTask } from '../../composables/publication'
import type { EditorScreen, Option, StreamView, TaskView } from '../../../shared/types/api'

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
/** The task ID of a publication lives until its request gets through, so a repeat is the same task (R-TK-04). */
const taskIds = new Map<string, string>()

function request(streamId: string, command: StreamCommand): [string, ApiRequest] {
  const stream = `/api/streams/${streamId}`
  switch (command.action) {
    case 'add': return [`${stream}/offers`, { method: 'POST', body: { offerId: command.offerId } }]
    case 'remove': return [`${stream}/offers/${command.offerId}`, { method: 'DELETE' }]
    case 'restore': return [`${stream}/offers/${command.offerId}/restore`, { method: 'POST' }]
    case 'pin': return [`${stream}/offers/${command.offerId}/pin`, { method: 'PUT', body: { share: command.share } }]
    case 'unpin': return [`${stream}/offers/${command.offerId}/pin`, { method: 'DELETE' }]
    case 'cancel': return [`${stream}/cancel`, { method: 'POST' }]
    case 'push': {
      const taskId = taskIds.get(streamId) ?? crypto.randomUUID()
      taskIds.set(streamId, taskId)
      return [`${stream}/push`, { method: 'POST', body: { taskId } }]
    }
  }
}

function show(updated: StreamView) {
  if (!screen.value) return
  screen.value = {
    ...screen.value,
    streams: screen.value.streams.map(stream => (stream.id === updated.id ? updated : stream)),
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
    const version = screen.value.streams.find(stream => stream.id === streamId)?.version
    const versioned = version === undefined ? options : { ...options, query: { version } }
    if (command.action === 'push') await publish(streamId, await api<TaskView>(url, versioned))
    else show(await api<StreamView>(url, versioned))
  }
  catch (error) {
    const refusal = toApiError(error)
    // the request was answered: the next publication is a new task
    if (refusal.code !== 'network') taskIds.delete(streamId)
    // Another window changed the stream: show what it is now, next to the reason (R-UX-17).
    if (refusal.stream) show(refusal.stream)
    errors.value = { ...errors.value, [streamId]: refusal.message }
  }
  finally {
    const { [streamId]: _done, ...rest } = pending.value
    pending.value = rest
  }
}

/** The publication was queued: wait for its end and show what became of the stream (R-UX-18). */
async function publish(streamId: string, queued: TaskView) {
  taskIds.delete(streamId)
  const task = queued.finished
    ? queued
    : await followTask(queued.id, { load: id => api<TaskView>(`/api/tasks/${id}`) })
  const fresh = await api<EditorScreen>(`/api/campaigns/${campaignId}/editor`)
  const stream = fresh.streams.find(item => item.id === streamId)
  if (stream) show(stream)
  if (!task) errors.value = { ...errors.value, [streamId]: 'Публикация ещё выполняется. Обновите страницу позже.' }
  else if (task.status === 'rejected') errors.value = { ...errors.value, [streamId]: task.refusal ?? 'Публикация отклонена' }
}

/** A publication that was running when the page opened is followed to its end too. */
async function resume(stream: StreamView) {
  if (!stream.publishingTaskId || pending.value[stream.id]) return
  pending.value = { ...pending.value, [stream.id]: 'push' }
  try {
    await publish(stream.id, await api<TaskView>(`/api/tasks/${stream.publishingTaskId}`))
  }
  catch (error) {
    errors.value = { ...errors.value, [stream.id]: toApiError(error).message }
  }
  finally {
    const { [stream.id]: _done, ...rest } = pending.value
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

onMounted(() => {
  screen.value?.streams.filter(stream => stream.acceptsOffers).forEach(stream => searchOffers(stream.id, ''))
  screen.value?.streams.forEach(stream => resume(stream))
})
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
