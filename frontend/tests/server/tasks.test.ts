import { describe, expect, it } from 'vitest'
import { cancelTask, loadTasks, retryTask } from '../../server/utils/tasks'
import { TASK_ID, fakeBackend, refusal, task } from './support'

const NEW_ID = '7c1d2e3f-4a5b-4c6d-8e7f-9a0b1c2d3e4f'
const QUEUE = {
  tasks: [{ status: 'PENDING', count: 1 }, { status: 'REJECTED', count: 2 }],
  outboxWaiting: 1,
  outboxOldest: '2026-11-17T12:00:00+00:00',
  queues: [{ name: 'keitaro.tasks', ready: 1, consumers: 0 }],
}

describe('tasks screen', () => {
  it('answers with the state of the queue and the tasks (R-UX-30)', async () => {
    const { graphql, calls } = fakeBackend({ TasksScreen: { queueStatus: QUEUE, tasks: [task({ retryOf: 'old' })] } })

    const screen = await loadTasks(graphql, {})

    expect(calls).toEqual([{ operation: 'TasksScreen', variables: { statuses: undefined, first: 50 } }])
    expect(screen.queue).toEqual({
      tasks: [{ status: 'pending', count: 1 }, { status: 'rejected', count: 2 }],
      outboxWaiting: 1,
      outboxOldest: '2026-11-17T12:00:00+00:00',
      queues: [{ name: 'keitaro.tasks', ready: 1, consumers: 0 }],
    })
    expect(screen.tasks).toMatchObject([{ id: TASK_ID, status: 'pending', finished: false, retryOf: 'old' }])
  })

  it('narrows the list to one status', async () => {
    const { graphql, calls } = fakeBackend({ TasksScreen: { queueStatus: QUEUE, tasks: [] } })

    await loadTasks(graphql, { status: 'rejected' })

    expect(calls[0]?.variables).toEqual({ statuses: ['REJECTED'], first: 50 })
  })

  it('rejects an unknown status without asking the backend', async () => {
    const { graphql, calls } = fakeBackend({})

    expect((await refusal(loadTasks(graphql, { status: 'lost' }))).status).toBe(400)
    expect(calls).toHaveLength(0)
  })
})

describe('task actions', () => {
  it('cancels a task (R-TK-08)', async () => {
    const { graphql, calls } = fakeBackend({ CancelTask: { result: task({ status: 'CANCELLED' }) } })

    const view = await cancelTask(graphql, TASK_ID)

    expect(calls).toEqual([{ operation: 'CancelTask', variables: { id: TASK_ID } }])
    expect(view).toMatchObject({ status: 'cancelled', finished: true })
  })

  it('repeats a task under the ID the browser made (R-TK-09)', async () => {
    const { graphql, calls } = fakeBackend({ RetryTask: { result: task({ id: NEW_ID, retryOf: TASK_ID }) } })

    const view = await retryTask(graphql, TASK_ID, { taskId: NEW_ID })

    expect(calls).toEqual([{ operation: 'RetryTask', variables: { input: { taskId: TASK_ID, newTaskId: NEW_ID } } }])
    expect(view).toMatchObject({ id: NEW_ID, retryOf: TASK_ID })
  })

  it.each([
    ['CancelTask', 'TaskNotFound', 404, 'task_not_found'],
    ['CancelTask', 'TaskNotCancellable', 409, 'task_not_cancellable'],
    ['RetryTask', 'TaskNotFound', 404, 'task_not_found'],
    ['RetryTask', 'TaskNotRetryable', 409, 'task_not_retryable'],
    ['RetryTask', 'StreamBusy', 409, 'stream_busy'],
    ['RetryTask', 'KeitaroFailure', 502, 'keitaro_failure'],
    ['RetryTask', 'StreamNotFound', 404, 'stream_not_found'],
    ['RetryTask', 'EmptyStream', 422, 'empty_stream'],
    ['RetryTask', 'TaskKeyReused', 409, 'task_key_reused'],
  ])('%s maps %s to %i', async (operation, typename, status, code) => {
    const { graphql } = fakeBackend({ [operation]: { result: { __typename: typename, message: 'почему' } } })
    const action = operation === 'CancelTask'
      ? cancelTask(graphql, TASK_ID)
      : retryTask(graphql, TASK_ID, { taskId: NEW_ID })

    expect(await refusal(action)).toEqual({ status, body: { code, message: 'почему' } })
  })

  it('passes on the remarks about a creation that is no longer valid (R-TK-09)', async () => {
    const fields = [{ field: 'groupId', message: 'В Keitaro нет такой группы' }]
    const { graphql } = fakeBackend({
      RetryTask: { result: { __typename: 'ValidationFailed', message: 'Проверьте поля: groupId', fields } },
    })

    expect(await refusal(retryTask(graphql, TASK_ID, { taskId: NEW_ID }))).toEqual({
      status: 422,
      body: { code: 'validation_failed', message: 'Проверьте поля: groupId', fields },
    })
  })

  it('rejects malformed IDs without asking the backend', async () => {
    const { graphql, calls } = fakeBackend({})

    expect((await refusal(cancelTask(graphql, 'not-a-uuid'))).status).toBe(400)
    expect((await refusal(retryTask(graphql, TASK_ID, {}))).status).toBe(400)
    expect(calls).toHaveLength(0)
  })
})
