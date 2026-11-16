<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Option, StreamView } from '../../../shared/types/api'
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiCombobox from '../ui/UiCombobox.vue'
import UiNotice from '../ui/UiNotice.vue'
import OfferRow from './OfferRow.vue'
import ShareBar from './ShareBar.vue'

export type StreamCommand
  = | { action: 'add', offerId: number }
    | { action: 'remove' | 'restore' | 'unpin', offerId: number }
    | { action: 'pin', offerId: number, share: number }
    | { action: 'cancel' | 'push' }

const props = defineProps<{
  stream: StreamView
  /** Offers found for the "add" list. */
  offers: Option<number>[]
  offersLoading?: boolean
  /** The action whose request is running, if any. */
  pending?: StreamCommand['action'] | null
  /** The last refusal; the draft stays as it was (R-UX-16). */
  error?: string | null
}>()

const emit = defineEmits<{
  'command': [StreamCommand]
  'search-offers': [string]
}>()

const picked = ref<Option<number> | null>(null)
const locked = computed(() => Boolean(props.pending))
const taken = computed(() => props.stream.offers.map(offer => offer.offerId))
const headingId = computed(() => `stream-${props.stream.id}`)

function add(option: Option<number> | null) {
  if (!option) return
  emit('command', { action: 'add', offerId: option.id })
  picked.value = null
}
</script>

<template>
  <section
    class="stream"
    :class="{ 'stream--dirty': stream.dirty }"
    :aria-labelledby="headingId"
  >
    <header class="stream__head">
      <h2 :id="headingId">
        {{ stream.name }}
      </h2>
      <span class="data stream__id">поток {{ stream.position }} · ID {{ stream.keitaroId }}</span>
      <UiBadge
        v-if="stream.dirty"
        tone="accent"
      >
        Не опубликовано
      </UiBadge>
    </header>

    <p
      v-if="!stream.acceptsOffers"
      class="small"
    >
      Поток без офферов: он перенаправляет посетителей и в редакторе не меняется.
    </p>
    <template v-else>
      <UiNotice
        v-if="error"
        tone="risk"
        title="Действие не выполнено"
      >
        {{ error }}
      </UiNotice>

      <template v-if="stream.offers.length">
        <ShareBar
          :offers="stream.offers"
          :total="stream.total"
        />
        <ul class="stream__offers">
          <OfferRow
            v-for="offer in stream.offers"
            :key="offer.offerId"
            :offer="offer"
            :locked="locked"
            @pin="emit('command', { action: 'pin', offerId: offer.offerId, share: $event })"
            @unpin="emit('command', { action: 'unpin', offerId: offer.offerId })"
            @remove="emit('command', { action: 'remove', offerId: offer.offerId })"
            @restore="emit('command', { action: 'restore', offerId: offer.offerId })"
          />
        </ul>
      </template>
      <p
        v-else
        class="small"
      >
        В потоке нет офферов. Добавьте первый — он получит 100 %.
      </p>

      <UiCombobox
        class="stream__add"
        :model-value="picked"
        :label="`Добавить оффер в ${stream.name}`"
        :options="offers"
        :loading="offersLoading"
        :disabled-ids="taken"
        disabled-note="уже в потоке"
        placeholder="Название или ID оффера"
        remote
        show-id
        @update:model-value="add"
        @search="emit('search-offers', $event)"
      />

      <footer
        v-if="stream.dirty"
        class="stream__publish"
      >
        <p>
          Изменений: <span class="data">{{ stream.changes }}</span>
        </p>
        <div class="stream__buttons">
          <UiButton
            :disabled="locked"
            :busy="pending === 'cancel'"
            @click="emit('command', { action: 'cancel' })"
          >
            Отменить
          </UiButton>
          <UiButton
            variant="primary"
            :disabled="locked"
            :busy="pending === 'push'"
            @click="emit('command', { action: 'push' })"
          >
            Опубликовать
          </UiButton>
        </div>
      </footer>
    </template>
  </section>
</template>

<style scoped>
.stream {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-2);
  padding: var(--gap-3);
  border: 1px solid var(--hair);
  border-left: 4px solid var(--hair);
  border-radius: var(--r-panel);
  background: var(--mist);
}

.stream--dirty {
  border-left-color: var(--acc-line);
}

.stream__head {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-1) var(--gap-2);
}

.stream__id {
  color: var(--cap);
}

.stream__offers {
  display: grid;
}

.stream__add {
  max-width: 520px;
}

.stream__publish {
  position: sticky;
  bottom: var(--gap-1);
  z-index: 5;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: var(--gap-1) var(--gap-2);
  padding: var(--gap-1) var(--gap-2);
  border: 1px solid var(--acc-line);
  border-radius: var(--r-box);
  background: var(--ground);
  box-shadow: var(--shade);
}

.stream__buttons {
  display: flex;
  gap: var(--gap-1);
}

@media (max-width: 599px) {
  .stream {
    padding: var(--gap-2);
  }
}
</style>
