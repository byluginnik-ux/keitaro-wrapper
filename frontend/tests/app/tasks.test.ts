// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import TasksBoard from '../../app/components/tasks/TasksBoard.vue'
import type { QueueView, TaskView, TasksScreen } from '../../shared/types/api'

function task(patch: Partial<TaskView> = {}): TaskView {
  return {
    id: 'task-1',
    kind: 'publish_stream',
    status: 'pending',
    finished: false,
    attempts: 0,
    createdAt: '2026-11-17T12:00:00+00:00',
    startedAt: null,
    finishedAt: null,
    campaignId: 'c-1',
    streamId: 's-2',
    retryOf: null,
    refusal: null,
    steps: [{ name: 'queued', at: '2026-11-17T12:00:00+00:00', note: '' }],
    ...patch,
  }
}

function board(tasks: TaskView[], queue: Partial<QueueView> = {}, props: Record<string, unknown> = {}) {
  const screen: TasksScreen = {
    queue: {
      tasks: [{ status: 'pending', count: 1 }, { status: 'rejected', count: 2 }],
      outboxWaiting: 3,
      outboxOldest: null,
      queues: [{ name: 'keitaro.tasks', ready: 4, consumers: 2 }],
      ...queue,
    },
    tasks,
  }
  return mount(TasksBoard, {
    props: { screen, filter: null, ...props },
    global: { stubs: { NuxtLink: { template: '<a><slot /></a>' } } },
  })
}

/** The text without whitespace: how the markup is wrapped is not what is tested. */
const compact = (wrapper: { text: () => string }) => wrapper.text().replace(/\s+/g, '')

describe('tasks board (R-UX-30, R-UX-31)', () => {
  it('shows the state of the queue in numbers', () => {
    const text = compact(board([]))

    expect(text).toContain('Ожидает1')
    expect(text).toContain('Отклонена2')
    expect(text).toContain('Выполнена0')
    expect(text).toContain('Неотправленосообщений3')
    expect(text).toContain('keitaro.tasks:ждёт4,обработчиков2')
    expect(text).toContain('Задачнет.')
    expect(board([]).find('[role="alert"]').exists()).toBe(false)
  })

  it('warns in words when nobody listens to a queue', () => {
    const wrapper = board([], { queues: [{ name: 'keitaro.tasks', ready: 1, consumers: 0 }] })

    expect(wrapper.text()).toContain('обработчиков нет')
    expect(wrapper.text()).toContain('Очередь keitaro.tasks никто не слушает')
  })

  it('shows a task with its status, attempts, reason and steps', () => {
    const rejected = task({
      status: 'rejected',
      finished: true,
      attempts: 3,
      retryOf: 'task-0',
      refusal: 'Keitaro ответил 502',
      steps: [
        { name: 'queued', at: '2026-11-17T12:00:00+00:00', note: '' },
        { name: 'attempt', at: '2026-11-17T12:00:01+00:00', note: '1' },
        { name: 'rejected', at: '2026-11-17T12:00:09+00:00', note: '' },
      ],
    })
    const text = compact(board([rejected]))

    expect(text).toContain('Публикацияпотока')
    expect(text).toContain('попыток3')
    expect(text).toContain('повторtask-0')
    expect(text).toContain('Причина:Keitaroответил502')
    expect(text).toContain('12:00:01UTCПопытка1')
  })

  it('offers to cancel a waiting task and to repeat a rejected publication', async () => {
    const waiting = task()
    const rejected = task({ id: 'task-2', status: 'rejected', finished: true })
    const done = task({ id: 'task-3', status: 'succeeded', finished: true })
    const campaign = task({ id: 'task-4', kind: 'create_campaign', status: 'rejected', finished: true })
    const wrapper = board([waiting, rejected, done, campaign])

    const buttons = wrapper.findAll('button')
    await buttons[0]?.trigger('click')
    await buttons[1]?.trigger('click')

    expect(buttons.map(item => item.text())).toEqual(['Отменить задачу task-1', 'Повторить задачу task-2'])
    expect(wrapper.emitted('cancel')).toEqual([[waiting]])
    expect(wrapper.emitted('retry')).toEqual([[rejected]])
  })

  it('locks the button of a running request and shows the refusal at its task', () => {
    const wrapper = board([task()], {}, { pending: { 'task-1': 'cancel' }, errors: { 'task-1': 'Уже выполняется' } })

    expect(wrapper.find('button').attributes('aria-busy')).toBe('true')
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.find('[data-task="task-1"]').text()).toContain('Уже выполняется')
  })

  it('asks for another status', async () => {
    const wrapper = board([])

    await wrapper.find('select').setValue('rejected')
    await wrapper.find('select').setValue('')

    expect(wrapper.emitted('filter')).toEqual([['rejected'], [null]])
  })
})
