<script setup lang="ts">
import { api, toApiError } from '../composables/api'
import type { CampaignView, EditorScreen } from '../../shared/types/api'

useHead({ title: 'Кампании — Keitaro Wrapper' })

const { data: campaigns, error: listError, status, refresh } = await useAsyncData(
  'campaigns',
  () => api<CampaignView[]>('/api/campaigns'),
)

const keitaroId = ref('')
const opening = ref(false)
const openError = ref<string | null>(null)

/** A campaign the service has not seen yet is read from the tracker and remembered (R-ED-07). */
async function open() {
  const id = keitaroId.value.trim()
  if (!/^\d+$/.test(id)) {
    openError.value = 'Введите ID кампании — целое число, как в адресе кампании в Keitaro'
    return
  }
  const known = campaigns.value?.find(campaign => campaign.keitaroId === Number(id))
  if (known) return navigateTo(`/campaigns/${known.id}`)
  opening.value = true
  openError.value = null
  try {
    const screen = await api<EditorScreen>('/api/campaigns/fetch', { method: 'POST', body: { keitaroId: Number(id) } })
    await navigateTo(`/campaigns/${screen.campaign.id}`)
  }
  catch (error) {
    openError.value = toApiError(error).message
  }
  finally {
    opening.value = false
  }
}
</script>

<template>
  <section class="page">
    <header>
      <h1>Кампании</h1>
      <p class="small">
        Кампании, созданные здесь или открытые по ID. Редактор меняет офферы в их потоках.
      </p>
    </header>

    <form
      class="open"
      novalidate
      @submit.prevent="open"
    >
      <UiField
        v-model="keitaroId"
        class="open__field"
        label="Открыть кампанию из Keitaro"
        placeholder="ID кампании, например 93212"
        inputmode="numeric"
        :error="openError ?? undefined"
      />
      <UiButton
        type="submit"
        :busy="opening"
      >
        Открыть
      </UiButton>
      <NuxtLink
        class="open__create"
        to="/create"
      >Создать новую</NuxtLink>
    </form>

    <p
      v-if="status === 'pending'"
      role="status"
    >
      Загрузка кампаний…
    </p>
    <UiNotice
      v-else-if="listError"
      tone="risk"
      title="Список не загрузился"
    >
      <p>{{ toApiError(listError).message }}</p>
      <div>
        <UiButton @click="refresh()">
          Повторить
        </UiButton>
      </div>
    </UiNotice>
    <UiNotice
      v-else-if="!campaigns?.length"
      title="Кампаний пока нет"
    >
      Создайте кампанию или откройте существующую по её ID в Keitaro.
    </UiNotice>
    <ul
      v-else
      class="list"
    >
      <li
        v-for="campaign in campaigns"
        :key="campaign.id"
        class="list__item"
      >
        <NuxtLink
          class="list__name"
          :to="`/campaigns/${campaign.id}`"
        >{{ campaign.name }}</NuxtLink>
        <span class="data list__meta">ID {{ campaign.keitaroId }}<template v-if="campaign.country"> · {{ campaign.country }}</template></span>
        <a
          class="small"
          :href="campaign.trackerLink"
          target="_blank"
          rel="noopener"
        >В Keitaro<span class="visually-hidden"> (в новой вкладке): {{ campaign.name }}</span></a>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-3);
}

.open {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: var(--gap-1) var(--gap-2);
}

.open__field {
  flex: 1 1 260px;
  max-width: 420px;
}

.open > :not(.open__field) {
  margin-top: 28px;
}

.open__create {
  display: inline-flex;
  align-items: center;
  min-height: var(--control);
  font-weight: 600;
}

.list {
  display: grid;
}

.list__item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px var(--gap-2);
  min-height: var(--control-lg);
  padding: var(--gap-1) 0;
  border-top: 1px solid var(--hair);
}

.list__name {
  flex: 1 1 240px;
  min-width: 0;
  overflow-wrap: anywhere;
  color: var(--ink);
  font-weight: 600;
}

.list__meta {
  color: var(--cap);
}
</style>
