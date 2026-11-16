<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { OfferView } from '../../../shared/types/api'
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'

const props = defineProps<{
  offer: OfferView
  /** A request of the stream is running: nothing can be pressed. */
  locked?: boolean
}>()

const emit = defineEmits<{
  pin: [share: number]
  unpin: []
  remove: []
  restore: []
}>()

const editing = ref(false)
const draft = ref('')
const invalid = ref(false)
const field = ref<HTMLInputElement | null>(null)
const opener = ref<HTMLButtonElement | null>(null)

async function edit() {
  draft.value = String(props.offer.share)
  invalid.value = false
  editing.value = true
  await nextTick()
  field.value?.select()
}

async function leave(refocus: boolean) {
  editing.value = false
  if (!refocus) return
  await nextTick()
  opener.value?.focus()
}

function confirm() {
  if (!/^\d+$/.test(draft.value.trim())) {
    invalid.value = true
    return
  }
  emit('pin', Number(draft.value.trim()))
  void leave(true)
}

function togglePin() {
  if (props.offer.pinned) emit('unpin')
  else emit('pin', props.offer.share)
}
</script>

<template>
  <li
    class="row"
    :class="{ 'row--removed': offer.removed }"
  >
    <div class="row__name">
      <span>{{ offer.name }}</span>
      <UiBadge
        v-if="offer.removed"
        tone="muted"
      >
        Удалён
      </UiBadge>
      <UiBadge
        v-else-if="offer.isNew"
        tone="accent"
      >
        Новый
      </UiBadge>
    </div>

    <div class="row__share">
      <span
        v-if="offer.changed && offer.publishedShare !== null"
        class="row__was data"
      >
        <span class="visually-hidden">Было </span>{{ offer.publishedShare }}<span aria-hidden="true"> → </span><span class="visually-hidden">, стало </span>
      </span>
      <span
        v-if="offer.removed"
        class="row__value data"
      >0 %</span>
      <template v-else-if="editing">
        <input
          ref="field"
          v-model="draft"
          class="row__input data"
          type="text"
          inputmode="numeric"
          :aria-label="`Доля оффера ${offer.name}, %`"
          :aria-invalid="invalid || undefined"
          @keydown.enter.prevent="confirm"
          @keydown.esc.prevent="leave(true)"
          @blur="leave(false)"
        >
        <span
          class="data"
          aria-hidden="true"
        >%</span>
      </template>
      <button
        v-else
        ref="opener"
        class="row__value row__value--button data"
        type="button"
        :disabled="locked"
        :aria-label="`Доля оффера ${offer.name}: ${offer.share} %. Изменить`"
        @click="edit"
      >
        {{ offer.share }} %
      </button>
    </div>

    <div class="row__actions">
      <template v-if="offer.removed">
        <UiButton
          :disabled="locked"
          :aria-label="`Вернуть ${offer.name}`"
          @click="emit('restore')"
        >
          Вернуть
        </UiButton>
      </template>
      <template v-else>
        <button
          class="row__pin"
          :class="{ 'row__pin--on': offer.pinned }"
          type="button"
          :disabled="locked"
          :aria-pressed="offer.pinned"
          :aria-label="offer.pinned ? `Доля закреплена: ${offer.name}. Открепить` : `Закрепить долю: ${offer.name}`"
          :title="offer.pinned ? 'Доля закреплена' : 'Закрепить долю'"
          @click="togglePin"
        >
          <svg
            viewBox="0 0 16 16"
            width="16"
            height="16"
            aria-hidden="true"
          >
            <rect
              x="3"
              y="7"
              width="10"
              height="7"
              rx="1.5"
            />
            <path
              v-if="offer.pinned"
              d="M5 7V5a3 3 0 0 1 6 0v2"
            />
            <path
              v-else
              d="M5 7V5a3 3 0 0 1 5.6-1.5"
            />
          </svg>
        </button>
        <UiButton
          variant="danger"
          :disabled="locked"
          :aria-label="`Удалить ${offer.name}`"
          @click="emit('remove')"
        >
          Удалить
        </UiButton>
      </template>
    </div>
  </li>
</template>

<style scoped>
.row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--gap-1) var(--gap-2);
  padding: var(--gap-1) 0;
  border-top: 1px solid var(--hair);
}

.row--removed .row__name,
.row--removed .row__value {
  color: var(--cap);
}

.row--removed .row__name > span:first-child {
  text-decoration: line-through;
}

.row__name {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px var(--gap-1);
  min-width: 0;
  overflow-wrap: anywhere;
}

.row__share {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 4px;
  min-width: 108px;
}

.row__was {
  color: var(--cap);
}

.row__value {
  min-width: 56px;
  text-align: right;
}

.row__value--button {
  min-height: var(--control);
  padding: 0 10px;
  border: 1px dashed var(--line);
  border-radius: var(--r-box);
  background: transparent;
  cursor: text;
  transition: background-color var(--ease);
}

.row__value--button:hover:not(:disabled) {
  background: var(--tint);
}

.row__input {
  width: 56px;
  height: var(--control);
  padding: 0 8px;
  border: 1px solid var(--acc-line);
  border-radius: var(--r-box);
  background: var(--ground);
  text-align: right;
}

.row__input[aria-invalid="true"] {
  border-color: var(--risk-deep);
}

.row__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--gap-1);
}

.row__pin {
  display: inline-grid;
  place-items: center;
  width: var(--control);
  height: var(--control);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--cap);
  cursor: pointer;
  transition: background-color var(--ease);
}

.row__pin svg {
  fill: none;
  stroke: currentColor;
  stroke-width: 1.5;
  stroke-linecap: round;
}

.row__pin--on {
  border-color: var(--ink);
  background: var(--ink);
  color: var(--ground);
}

.row__pin--on rect {
  fill: currentColor;
}

.row__pin:disabled,
.row__value--button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

@media (max-width: 599px) {
  .row {
    grid-template-columns: minmax(0, 1fr) auto;
  }

  .row__name {
    grid-column: 1 / -1;
  }

  .row__share {
    justify-content: flex-start;
  }
}
</style>
