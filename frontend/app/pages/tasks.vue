<script setup lang="ts">
import { api, toApiError } from '../composables/api'
import type { TaskStatus, TaskView, TasksScreen } from '../../shared/types/api'

useHead({ title: 'Задачи — Keitaro Wrapper' })

const REFRESH_MS = 3000

const filter = ref<TaskStatus | null>(null)
const load = () => api<TasksScreen>('/api/tasks', filter.value ? { query: { status: filter.value } } : {})

const { data: screen, error: loadError, status, refresh } = await useAsyncData('tasks', load)

const pending = ref<Record<string, 'cancel' | 'retry'>>({})
const errors = ref<Record<string, string>>({})
const refreshError = ref<string | null>(null)
const reloading = ref(false)
/** The ID of the repeating task lives until its request is answered, so a resend is the same task (R-TK-04). */
const retryIds = new Map<string, string>()

/** Read the page again; a failure keeps what is shown (R-UX-32). */
async function reload() {
  if (reloading.value) return
  reloading.value = true
  try {
    screen.value = await load()
    refreshError.value = null
  }
  catch (error) {
    refreshError.value = toApiError(error).message
  }
  finally {
    reloading.value = false
  }
}

async function act(task: TaskView, action: 'cancel' | 'retry') {
  if (pending.value[task.id]) return
  pending.value = { ...pending.value, [task.id]: action }
  const { [task.id]: _old, ...others } = errors.value
  errors.value = others
  try {
    if (action === 'cancel') {
      await api<TaskView>(`/api/tasks/${task.id}/cancel`, { method: 'POST' })
    }
    else {
      const taskId = retryIds.get(task.id) ?? crypto.randomUUID()
      retryIds.set(task.id, taskId)
      await api<TaskView>(`/api/tasks/${task.id}/retry`, { method: 'POST', body: { taskId } })
      retryIds.delete(task.id)
    }
  }
  catch (error) {
    const refusal = toApiError(error)
    if (refusal.code !== 'network') retryIds.delete(task.id)
    errors.value = { ...errors.value, [task.id]: refusal.message }
  }
  finally {
    const { [task.id]: _done, ...rest } = pending.value
    pending.value = rest
  }
  await reload()
}

function narrow(next: TaskStatus | null) {
  filter.value = next
  return reload()
}

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  timer = setInterval(reload, REFRESH_MS)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <section class="page">
    <header class="page__head">
      <div>
        <h1>Задачи</h1>
        <p class="small">
          Изменения в Keitaro выполняются задачами. Страница обновляется сама.
        </p>
      </div>
      <UiButton
        :busy="reloading"
        @click="reload"
      >
        Обновить
      </UiButton>
    </header>

    <p
      v-if="status === 'pending'"
      role="status"
    >
      Загрузка задач…
    </p>
    <UiNotice
      v-else-if="loadError || !screen"
      tone="risk"
      title="Задачи не загрузились"
    >
      <p>{{ toApiError(loadError).message }}</p>
      <div>
        <UiButton @click="refresh()">
          Повторить
        </UiButton>
      </div>
    </UiNotice>
    <template v-else>
      <UiNotice
        v-if="refreshError"
        tone="risk"
        title="Страница не обновилась"
      >
        {{ refreshError }} Показано то, что было получено раньше.
      </UiNotice>
      <TasksBoard
        :screen="screen"
        :filter="filter"
        :pending="pending"
        :errors="errors"
        @cancel="act($event, 'cancel')"
        @retry="act($event, 'retry')"
        @filter="narrow"
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
</style>
