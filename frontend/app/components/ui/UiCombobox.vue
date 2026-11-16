<script setup lang="ts" generic="T extends string | number">
import { computed, ref, useId, watch } from 'vue'

export interface ComboOption<Id> {
  id: Id
  name: string
}

const props = defineProps<{
  label: string
  options: ComboOption<T>[]
  modelValue: ComboOption<T> | null
  placeholder?: string
  error?: string
  hint?: string
  /** Options are searched by the server: typing emits `search` instead of filtering here. */
  remote?: boolean
  loading?: boolean
  /** Options that are listed but cannot be chosen, with the reason shown next to them. */
  disabledIds?: T[]
  disabledNote?: string
  /** Show the identifier next to the name. */
  showId?: boolean
  /** When set, text that matches no option is offered as a new item. */
  createLabel?: (text: string) => string
}>()

const emit = defineEmits<{
  'update:modelValue': [ComboOption<T> | null]
  'search': [string]
  'create': [string]
}>()

const id = useId()
const text = ref(props.modelValue?.name ?? '')
const open = ref(false)
const active = ref(0)
const typed = ref(false)

watch(() => props.modelValue, (value) => {
  text.value = value?.name ?? ''
  typed.value = false
})

const needle = computed(() => (typed.value ? text.value.trim().toLocaleLowerCase() : ''))

const visible = computed(() => {
  if (props.remote || !needle.value) return props.options
  return props.options.filter(option =>
    option.name.toLocaleLowerCase().includes(needle.value)
    || String(option.id).toLocaleLowerCase().startsWith(needle.value),
  )
})

const creatable = computed(() => {
  if (!props.createLabel || !needle.value) return null
  const exact = props.options.some(option => option.name.toLocaleLowerCase() === needle.value)
  return exact ? null : text.value.trim()
})

const count = computed(() => visible.value.length + (creatable.value ? 1 : 0))
const activeId = computed(() => (open.value && count.value ? `${id}-option-${active.value}` : undefined))

function isDisabled(option: ComboOption<T>) {
  return props.disabledIds?.includes(option.id) ?? false
}

function show() {
  open.value = true
  active.value = 0
}

function close() {
  open.value = false
  typed.value = false
  text.value = props.modelValue?.name ?? ''
}

function onInput(event: Event) {
  text.value = (event.target as HTMLInputElement).value
  typed.value = true
  show()
  if (props.remote) emit('search', text.value.trim())
  if (!text.value && props.modelValue) emit('update:modelValue', null)
}

function choose(index: number) {
  const option = visible.value[index]
  if (option) {
    if (isDisabled(option)) return
    emit('update:modelValue', option)
    text.value = option.name
  }
  else if (creatable.value) {
    emit('create', creatable.value)
  }
  else {
    return
  }
  open.value = false
  typed.value = false
}

function move(step: number) {
  if (!open.value) return show()
  if (count.value) active.value = (active.value + step + count.value) % count.value
}

function onKeydown(event: KeyboardEvent) {
  switch (event.key) {
    case 'ArrowDown':
      event.preventDefault()
      return move(1)
    case 'ArrowUp':
      event.preventDefault()
      return move(-1)
    case 'Enter':
      if (!open.value) return
      event.preventDefault()
      // the list still shows the answer to an earlier search
      if (props.remote && props.loading) return
      return choose(active.value)
    case 'Escape':
      if (!open.value) return
      event.preventDefault()
      return close()
  }
}
</script>

<template>
  <div class="combo">
    <label
      class="combo__label"
      :for="id"
    >{{ label }}</label>
    <div class="combo__anchor">
      <input
        :id="id"
        class="combo__input"
        :class="{ 'combo__input--error': error }"
        type="text"
        role="combobox"
        autocomplete="off"
        aria-autocomplete="list"
        :aria-expanded="open"
        :aria-controls="`${id}-list`"
        :aria-activedescendant="activeId"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="error ? `${id}-error` : hint ? `${id}-hint` : undefined"
        :placeholder="placeholder"
        :value="text"
        @focus="show"
        @click="show"
        @input="onInput"
        @keydown="onKeydown"
        @blur="close"
      >
      <ul
        v-show="open"
        :id="`${id}-list`"
        class="combo__list"
        role="listbox"
        :aria-label="label"
      >
        <li
          v-for="(option, index) in visible"
          :id="`${id}-option-${index}`"
          :key="option.id"
          class="combo__option"
          :class="{ 'combo__option--active': index === active, 'combo__option--disabled': isDisabled(option) }"
          role="option"
          :aria-selected="option.id === modelValue?.id"
          :aria-disabled="isDisabled(option) || undefined"
          @mousedown.prevent
          @click="choose(index)"
          @mousemove="active = index"
        >
          <span class="combo__name">{{ option.name }}</span>
          <span
            v-if="isDisabled(option) && disabledNote"
            class="combo__note"
          >{{ disabledNote }}</span>
          <span
            v-else-if="showId"
            class="combo__note data"
          >{{ option.id }}</span>
        </li>
        <li
          v-if="creatable"
          :id="`${id}-option-${visible.length}`"
          class="combo__option combo__option--create"
          :class="{ 'combo__option--active': active === visible.length }"
          role="option"
          aria-selected="false"
          @mousedown.prevent
          @click="choose(visible.length)"
          @mousemove="active = visible.length"
        >
          {{ createLabel?.(creatable) }}
        </li>
        <li
          v-if="!count"
          class="combo__empty"
          role="presentation"
        >
          {{ loading ? 'Поиск…' : 'Ничего не найдено' }}
        </li>
      </ul>
    </div>
    <p
      v-if="error"
      :id="`${id}-error`"
      class="combo__error"
    >
      {{ error }}
    </p>
    <p
      v-else-if="hint"
      :id="`${id}-hint`"
      class="small"
    >
      {{ hint }}
    </p>
  </div>
</template>

<style scoped>
.combo {
  display: grid;
  align-content: start;
  gap: 6px;
  min-width: 0;
}

.combo__label {
  font-weight: 600;
}

.combo__anchor {
  position: relative;
}

.combo__input {
  width: 100%;
  height: var(--control);
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--r-box);
  background: var(--ground);
  transition: border-color var(--ease);
}

.combo__input--error {
  border-color: var(--risk-deep);
}

.combo__list {
  position: absolute;
  z-index: 10;
  top: calc(100% + 4px);
  left: 0;
  right: 0;
  max-height: 280px;
  overflow-y: auto;
  padding: 4px;
  border: 1px solid var(--hair);
  border-radius: var(--r-box);
  background: var(--ground);
  box-shadow: var(--shade);
}

.combo__option {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--gap-2);
  min-height: var(--control);
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
}

.combo__option--active {
  background: var(--tint);
}

.combo__option[aria-selected="true"] {
  box-shadow: inset 3px 0 0 var(--acc-line);
}

.combo__option--disabled {
  color: var(--cap);
  cursor: not-allowed;
}

.combo__option--create {
  color: var(--acc-text);
  font-weight: 600;
}

.combo__name {
  min-width: 0;
  overflow-wrap: anywhere;
}

.combo__note {
  flex: none;
  color: var(--cap);
  font-size: 0.8125rem;
}

.combo__empty {
  padding: 10px 12px;
  color: var(--cap);
}

.combo__error {
  color: var(--risk-text);
  font-size: 0.875rem;
  line-height: 1.25rem;
}
</style>
