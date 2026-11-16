<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { CreatorOptions, FieldRemark, Option } from '../../../shared/types/api'
import UiButton from '../ui/UiButton.vue'
import UiCombobox from '../ui/UiCombobox.vue'
import UiField from '../ui/UiField.vue'
import UiNotice from '../ui/UiNotice.vue'

export interface CampaignDraft {
  name: string
  country: string
  offerId: number
  groupId: number
  trafficSourceId: number
  domainId?: number
  newDomainName?: string
}

type Field = 'name' | 'country' | 'offer' | 'domain' | 'group' | 'source'

const props = defineProps<{
  options: CreatorOptions
  offers: Option<number>[]
  offersLoading?: boolean
  busy?: boolean
  /** Remarks of the server, each about one field of the input (R-UX-03). */
  remarks?: FieldRemark[]
  /** A refusal that is about no particular field, such as a tracker failure. */
  failure?: string | null
}>()

const emit = defineEmits<{
  'submit': [CampaignDraft]
  'search-offers': [string]
}>()

const NEW_DOMAIN = -1
const SERVER_FIELDS: Record<string, Field> = {
  name: 'name',
  country: 'country',
  offerId: 'offer',
  groupId: 'group',
  trafficSourceId: 'source',
  domainId: 'domain',
  newDomainName: 'domain',
}
const REQUIRED: Record<Field, string> = {
  name: 'Введите продолжение названия',
  country: 'Выберите страну',
  offer: 'Выберите оффер',
  domain: 'Выберите домен или введите имя нового',
  group: 'Выберите группу',
  source: 'Выберите источник',
}

/** A list with a single item leaves nothing to choose. */
function only<T>(options: Option<T>[]): Option<T> | null {
  return options.length === 1 ? (options[0] ?? null) : null
}

const nameTail = ref('')
const country = ref<Option<string> | null>(null)
const offer = ref<Option<number> | null>(null)
const domain = ref<Option<number> | null>(only(props.options.domains))
const group = ref<Option<number> | null>(only(props.options.groups))
const source = ref<Option<number> | null>(only(props.options.trafficSources))
const attempted = ref(false)
const edited = ref(new Set<Field>())

const isNewDomain = computed(() => domain.value?.id === NEW_DOMAIN)
const domains = computed(() => (isNewDomain.value && domain.value ? [...props.options.domains, domain.value] : props.options.domains))

const missing = computed(() => {
  const empty = new Set<Field>()
  if (!nameTail.value.trim()) empty.add('name')
  if (!country.value) empty.add('country')
  if (!offer.value) empty.add('offer')
  if (!domain.value) empty.add('domain')
  if (!group.value) empty.add('group')
  if (!source.value) empty.add('source')
  return empty
})

// a remark of the server stands until the user changes the field it is about
watch(() => props.remarks, () => edited.value.clear())
watch([nameTail, country, offer, domain, group, source], (now, before) => {
  const fields: Field[] = ['name', 'country', 'offer', 'domain', 'group', 'source']
  fields.forEach((field, index) => now[index] !== before[index] && edited.value.add(field))
})

function errorOf(field: Field): string | undefined {
  if (attempted.value && missing.value.has(field)) return REQUIRED[field]
  if (edited.value.has(field)) return undefined
  return props.remarks?.find(remark => SERVER_FIELDS[remark.field] === field)?.message
}

function createDomain(text: string) {
  domain.value = { id: NEW_DOMAIN, name: text.toLowerCase() }
}

function submit() {
  attempted.value = true
  if (missing.value.size || !country.value || !offer.value || !domain.value || !group.value || !source.value) return
  emit('submit', {
    name: props.options.namePrefix + nameTail.value.trim(),
    country: country.value.id,
    offerId: offer.value.id,
    groupId: group.value.id,
    trafficSourceId: source.value.id,
    ...(isNewDomain.value ? { newDomainName: domain.value.name } : { domainId: domain.value.id }),
  })
}
</script>

<template>
  <form
    class="creator"
    novalidate
    @submit.prevent="submit"
  >
    <UiNotice
      v-if="failure"
      tone="risk"
      title="Кампания не создана"
    >
      {{ failure }}
    </UiNotice>

    <div class="creator__grid">
      <UiField
        v-model="nameTail"
        class="creator__wide"
        label="Название"
        :prefix="options.namePrefix"
        placeholder="au_flexacil"
        hint="Префикс обязателен для тестовых кампаний и не меняется"
        :error="errorOf('name')"
        required
      />
      <UiCombobox
        v-model="country"
        label="Страна"
        :options="options.countries"
        placeholder="Название или код, например AU"
        hint="Посетителей из этой страны поток 1 отправит на google.com"
        show-id
        :error="errorOf('country')"
      />
      <UiCombobox
        v-model="offer"
        label="Оффер"
        :options="offers"
        :loading="offersLoading"
        placeholder="Название или ID"
        hint="Все остальные попадут на него через поток 2"
        remote
        show-id
        :error="errorOf('offer')"
        @search="emit('search-offers', $event)"
      />
      <UiCombobox
        v-model="domain"
        label="Домен"
        :options="domains"
        placeholder="Выберите или введите новый"
        :hint="isNewDomain ? 'Новый домен: будет создан в Keitaro при отправке формы' : 'Существующий домен или имя нового, например tracker.example.com'"
        :create-label="text => `Создать домен ${text.toLowerCase()}`"
        :error="errorOf('domain')"
        @create="createDomain"
      />
      <UiCombobox
        v-model="group"
        label="Группа"
        :options="options.groups"
        placeholder="Группа кампаний"
        :error="errorOf('group')"
      />
      <UiCombobox
        v-model="source"
        label="Источник трафика"
        :options="options.trafficSources"
        placeholder="Источник"
        :error="errorOf('source')"
      />
    </div>

    <div class="creator__actions">
      <UiButton
        variant="primary"
        size="lg"
        type="submit"
        :busy="busy"
      >
        Создать кампанию
      </UiButton>
      <p class="small">
        Будут созданы кампания и два потока. При сбое кампания удаляется из Keitaro.
      </p>
    </div>
  </form>
</template>

<style scoped>
.creator {
  display: grid;
  gap: var(--gap-3);
  max-width: 880px;
}

.creator__grid {
  display: grid;
  gap: var(--gap-3) var(--gap-2);
}

@media (min-width: 720px) {
  .creator__grid {
    grid-template-columns: 1fr 1fr;
  }

  .creator__wide {
    grid-column: 1 / -1;
  }
}

.creator__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-2);
}
</style>
