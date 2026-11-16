<script setup lang="ts">
import { onMounted } from 'vue'
import { THEME_LABELS, useThemeMode } from '../../composables/theme'

const { mode, restore, cycle } = useThemeMode()
onMounted(restore)
</script>

<template>
  <button
    class="theme"
    type="button"
    @click="cycle"
  >
    <span class="theme__caption">Тема:</span> {{ THEME_LABELS[mode] }}
  </button>
</template>

<style scoped>
.theme {
  min-height: var(--control);
  padding: 0 var(--gap-2);
  border: 1px solid var(--hair);
  border-radius: var(--r-pill);
  background: transparent;
  font-size: 0.875rem;
  white-space: nowrap;
  cursor: pointer;
  transition: background-color var(--ease);
}

.theme:hover {
  background: var(--tint);
}

.theme__caption {
  color: var(--cap);
}
</style>
