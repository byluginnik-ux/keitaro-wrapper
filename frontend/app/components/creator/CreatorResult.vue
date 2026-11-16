<script setup lang="ts">
import type { CampaignView } from '../../../shared/types/api'
import UiButton from '../ui/UiButton.vue'
import UiNotice from '../ui/UiNotice.vue'

defineProps<{ campaign: CampaignView }>()
defineEmits<{ again: [] }>()
</script>

<template>
  <UiNotice
    tone="accent"
    title="Кампания создана"
  >
    <p>
      <strong>{{ campaign.name }}</strong>
      <span class="data result__id">ID в Keitaro: {{ campaign.keitaroId }}</span>
    </p>
    <p class="small">
      Поток 1 отправляет страну {{ campaign.country }} на google.com, поток 2 — на выбранный оффер.
    </p>
    <div class="result__links">
      <a
        class="result__link result__link--main"
        :href="`/campaigns/${campaign.id}`"
      >В редактор</a>
      <a
        class="result__link"
        :href="campaign.trackerLink"
        target="_blank"
        rel="noopener"
      >Открыть в Keitaro<span class="visually-hidden"> (в новой вкладке)</span></a>
      <UiButton
        variant="quiet"
        @click="$emit('again')"
      >
        Создать ещё одну
      </UiButton>
    </div>
  </UiNotice>
</template>

<style scoped>
.result__id {
  display: block;
  color: var(--cap);
}

.result__links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-1) var(--gap-2);
  margin-top: var(--gap-1);
}

.result__link {
  display: inline-flex;
  align-items: center;
  min-height: var(--control);
  padding: 0 var(--gap-2);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  color: var(--ink);
  font-weight: 600;
  text-decoration: none;
  transition: background-color var(--ease);
}

.result__link:hover {
  background: var(--tint);
}

.result__link--main {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--ground);
}

.result__link--main:hover {
  background: var(--cap);
}
</style>
