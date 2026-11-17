<script setup lang="ts">
import { computed } from 'vue'
import { stepLabel } from '../../composables/task-labels'
import type { TaskStatus, TaskView, TasksScreen } from '../../../shared/types/api'
import UiBadge from '../ui/UiBadge.vue'
import UiButton from '../ui/UiButton.vue'
import UiNotice from '../ui/UiNotice.vue'

const props = defineProps<{
  screen: TasksScreen
  /** The status the list is narrowed to; null — every task. */
  filter: TaskStatus | null
  /** Tasks whose request is running, by task ID. */
  pending?: Record<string, 'cancel' | 'retry'>
  /** The last refusal of an action, by task ID (R-UX-31). */
  errors?: Record<string, string>
}>()

const emit = defineEmits<{
  cancel: [TaskView]
  retry: [TaskView]
  filter: [TaskStatus | null]
}>()

const STATUSES: TaskStatus[] = ['pending', 'running', 'succeeded', 'rejected', 'cancelled']
const STATUS: Record<TaskStatus, string> = {
  pending: 'Ожидает',
  running: 'Выполняется',
  succeeded: 'Выполнена',
  rejected: 'Отклонена',
  cancelled: 'Отменена',
}
const KIND: Record<TaskView['kind'], string> = {
  publish_stream: 'Публикация потока',
  create_campaign: 'Создание кампании',
}

const counts = computed(() => STATUSES.map(status => ({
  status,
  count: props.screen.queue.tasks.find(item => item.status === status)?.count ?? 0,
})))
/** A queue nobody listens to keeps its tasks waiting: say so in words (R-UX-30). */
const idle = computed(() => props.screen.queue.queues.filter(queue => queue.consumers === 0))

function tone(status: TaskStatus) {
  if (status === 'rejected') return 'risk'
  return status === 'pending' || status === 'running' ? 'accent' : 'muted'
}

/** One clock for the server and the browser, so the page renders the same on both. */
function time(iso: string | null) {
  return iso ? `${new Date(iso).toISOString().slice(11, 19)} UTC` : '—'
}
</script>

<template>
  <div class="board">
    <section
      class="board__summary"
      aria-labelledby="queue-heading"
    >
      <h2 id="queue-heading">
        Очередь
      </h2>
      <dl class="board__numbers">
        <div
          v-for="item in counts"
          :key="item.status"
        >
          <dt>{{ STATUS[item.status] }}</dt>
          <dd class="data">
            {{ item.count }}
          </dd>
        </div>
        <div>
          <dt>Не отправлено сообщений</dt>
          <dd class="data">
            {{ screen.queue.outboxWaiting }}
          </dd>
        </div>
      </dl>
      <ul class="board__queues">
        <li
          v-for="queue in screen.queue.queues"
          :key="queue.name"
        >
          <span class="data">{{ queue.name }}</span>:
          ждёт <span class="data">{{ queue.ready }}</span>,
          <template v-if="queue.consumers">
            обработчиков <span class="data">{{ queue.consumers }}</span>
          </template>
          <strong v-else>обработчиков нет</strong>
        </li>
      </ul>
      <UiNotice
        v-if="idle.length"
        tone="risk"
        title="Обработчиков нет"
      >
        Очередь {{ idle.map(queue => queue.name).join(', ') }} никто не слушает: задачи будут ждать, пока не запустится обработчик.
      </UiNotice>
    </section>

    <section aria-labelledby="tasks-heading">
      <div class="board__head">
        <h2 id="tasks-heading">
          Задачи
        </h2>
        <label class="board__filter small">
          Статус
          <select
            :value="filter ?? ''"
            @change="emit('filter', (($event.target as HTMLSelectElement).value || null) as TaskStatus | null)"
          >
            <option value="">
              Все
            </option>
            <option
              v-for="status in STATUSES"
              :key="status"
              :value="status"
            >
              {{ STATUS[status] }}
            </option>
          </select>
        </label>
      </div>

      <p
        v-if="!screen.tasks.length"
        class="small"
      >
        Задач нет.
      </p>
      <ul
        v-else
        class="board__tasks"
      >
        <li
          v-for="task in screen.tasks"
          :key="task.id"
          class="task"
          :data-task="task.id"
        >
          <div class="task__head">
            <strong>{{ KIND[task.kind] }}</strong>
            <UiBadge :tone="tone(task.status)">
              {{ STATUS[task.status] }}
            </UiBadge>
            <span class="small data">поставлена {{ time(task.createdAt) }} · попыток {{ task.attempts }}</span>
            <NuxtLink
              v-if="task.campaignId"
              class="small"
              :to="`/campaigns/${task.campaignId}`"
            >Кампания</NuxtLink>
          </div>
          <p class="small data task__id">
            {{ task.id }}<template v-if="task.retryOf">
              · повтор {{ task.retryOf }}
            </template>
          </p>
          <p
            v-if="task.refusal"
            class="task__refusal"
          >
            Причина: {{ task.refusal }}
          </p>
          <ol class="task__steps small">
            <li
              v-for="(step, index) in task.steps"
              :key="index"
            >
              <span class="data">{{ time(step.at) }}</span> {{ stepLabel(step.name) }}<template v-if="step.note">
                {{ step.note }}
              </template>
            </li>
          </ol>
          <UiNotice
            v-if="errors?.[task.id]"
            tone="risk"
            title="Действие не выполнено"
          >
            {{ errors[task.id] }}
          </UiNotice>
          <div
            v-if="task.status === 'pending' || (task.status === 'rejected' && task.kind === 'publish_stream')"
            class="task__actions"
          >
            <UiButton
              v-if="task.status === 'pending'"
              :busy="pending?.[task.id] === 'cancel'"
              :disabled="Boolean(pending?.[task.id])"
              @click="emit('cancel', task)"
            >
              Отменить<span class="visually-hidden"> задачу {{ task.id }}</span>
            </UiButton>
            <UiButton
              v-else
              :busy="pending?.[task.id] === 'retry'"
              :disabled="Boolean(pending?.[task.id])"
              @click="emit('retry', task)"
            >
              Повторить<span class="visually-hidden"> задачу {{ task.id }}</span>
            </UiButton>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.board,
.board__summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-2);
}

.board {
  gap: var(--gap-3);
}

.board__numbers {
  display: flex;
  flex-wrap: wrap;
  gap: var(--gap-1) var(--gap-3);
  margin: 0;
}

.board__numbers dd {
  margin: 0;
  font-size: 1.25rem;
}

.board__queues,
.board__tasks,
.task__steps {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-1);
  margin: 0;
  padding: 0;
  list-style: none;
}

.board__head,
.task__head,
.task__actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--gap-1) var(--gap-2);
}

.board__head {
  justify-content: space-between;
  margin-bottom: var(--gap-2);
}

.board__filter {
  display: inline-flex;
  align-items: center;
  gap: var(--gap-1);
}

.board__tasks {
  gap: var(--gap-2);
}

.task {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: var(--gap-1);
  padding: var(--gap-2);
  border: 1px solid var(--hair);
  border-radius: var(--r-panel);
  background: var(--mist);
}

.task__id {
  margin: 0;
  overflow-wrap: anywhere;
}

.task__refusal {
  margin: 0;
}
</style>
