<script setup lang="ts">
import { computed } from 'vue'
import type { OfferView } from '../../../shared/types/api'

const props = defineProps<{ offers: OfferView[], total: number }>()

const active = computed(() => props.offers.filter(offer => !offer.removed))
const summary = computed(() => active.value.map(offer => `${offer.name} — ${offer.share} %`).join('; '))
</script>

<template>
  <div class="bar">
    <div
      class="bar__track"
      role="img"
      :aria-label="`Доли офферов: ${summary}`"
    >
      <span
        v-for="(offer, index) in active"
        :key="offer.offerId"
        class="bar__part"
        :class="{ 'bar__part--alt': index % 2 === 1, 'bar__part--changed': offer.changed }"
        :style="{ flexGrow: offer.share }"
      />
    </div>
    <p class="bar__total data">
      Сумма {{ total }} %
    </p>
  </div>
</template>

<style scoped>
.bar {
  display: flex;
  align-items: center;
  gap: var(--gap-2);
}

.bar__track {
  display: flex;
  flex: 1;
  gap: 2px;
  height: 12px;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--mist-2);
}

.bar__part {
  flex-basis: 0;
  min-width: 0;
  background: var(--ink);
  transition: flex-grow var(--ease);
}

.bar__part--alt {
  background: var(--cap);
}

.bar__part--changed {
  background: var(--acc-line);
}

.bar__total {
  flex: none;
  color: var(--cap);
}
</style>
