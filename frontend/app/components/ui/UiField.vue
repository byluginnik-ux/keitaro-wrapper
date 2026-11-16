<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(defineProps<{
  label: string
  modelValue: string
  /** A part of the value the user cannot change, shown inside the field (R-UX-01). */
  prefix?: string
  error?: string
  hint?: string
  placeholder?: string
  inputmode?: 'text' | 'numeric'
  required?: boolean
  disabled?: boolean
}>(), { inputmode: 'text' })

const emit = defineEmits<{ 'update:modelValue': [string] }>()

const id = useId()
const describedBy = computed(() => {
  const ids = [props.prefix && `${id}-prefix`, props.error && `${id}-error`, props.hint && `${id}-hint`]
  return ids.filter(Boolean).join(' ') || undefined
})

function onInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <div class="field">
    <label
      class="field__label"
      :for="id"
    >{{ label }}</label>
    <div
      class="field__box"
      :class="{ 'field__box--error': error }"
    >
      <span
        v-if="prefix"
        :id="`${id}-prefix`"
        class="field__prefix data"
      >{{ prefix }}</span>
      <input
        :id="id"
        class="field__input"
        :class="{ data: prefix || inputmode === 'numeric' }"
        type="text"
        :value="modelValue"
        :inputmode="inputmode"
        :placeholder="placeholder"
        :required="required"
        :disabled="disabled"
        :aria-invalid="error ? 'true' : undefined"
        :aria-describedby="describedBy"
        autocomplete="off"
        @input="onInput"
      >
    </div>
    <p
      v-if="error"
      :id="`${id}-error`"
      class="field__error"
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
.field {
  display: grid;
  gap: 6px;
  min-width: 0;
}

.field__label {
  font-weight: 600;
}

.field__box {
  display: flex;
  align-items: center;
  min-height: var(--control);
  border: 1px solid var(--line);
  border-radius: var(--r-box);
  background: var(--ground);
  transition: border-color var(--ease);
}

.field__box:focus-within {
  outline: 2px solid var(--acc-line);
  outline-offset: 2px;
}

.field__box--error {
  border-color: var(--risk-deep);
}

.field__prefix {
  padding-left: 12px;
  color: var(--cap);
  white-space: nowrap;
  user-select: none;
}

.field__input {
  flex: 1;
  min-width: 0;
  height: calc(var(--control) - 2px);
  padding: 0 12px;
  border: 0;
  border-radius: var(--r-box);
  background: transparent;
  outline: none;
}

.field__prefix + .field__input {
  padding-left: 0;
}

.field__error {
  color: var(--risk-text);
  font-size: 0.875rem;
  line-height: 1.25rem;
}
</style>
