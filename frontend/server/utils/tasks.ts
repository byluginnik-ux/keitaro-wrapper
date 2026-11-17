import type { TaskStatus as ContractStatus } from '@keitaro-wrapper/contracts'
import type { TaskStatus, TaskView, TasksScreen } from '../../shared/types/api'
import { CancelTaskDocument, RetryTaskDocument, TasksScreenDocument } from '../graphql/operations'
import { assertNever, fail } from './api-error'
import type { GraphqlClient } from './graphql'
import { parse, taskBody, taskFilter, taskRef } from './schemas'
import { toTaskView } from './views'

const LISTED = 50

/** The "Tasks" page in one answer: the state of the queue and the latest tasks (R-UX-30). */
export async function loadTasks(graphql: GraphqlClient, query: unknown): Promise<TasksScreen> {
  const { status } = parse(taskFilter, query)
  const statuses = status ? [status.toUpperCase() as ContractStatus] : undefined
  const { queueStatus, tasks } = await graphql(TasksScreenDocument, { statuses, first: LISTED })
  return {
    queue: {
      tasks: queueStatus.tasks.map(item => ({ status: item.status.toLowerCase() as TaskStatus, count: item.count })),
      outboxWaiting: queueStatus.outboxWaiting,
      outboxOldest: queueStatus.outboxOldest ?? null,
      queues: queueStatus.queues.map(item => ({ name: item.name, ready: item.ready, consumers: item.consumers })),
    },
    tasks: tasks.map(toTaskView),
  }
}

/** Take back a task nobody has started yet (R-TK-08). */
export async function cancelTask(graphql: GraphqlClient, id: unknown): Promise<TaskView> {
  const { taskId } = parse(taskRef, { taskId: id })
  const { result } = await graphql(CancelTaskDocument, { id: taskId })
  switch (result.__typename) {
    case 'Task':
      return toTaskView(result)
    case 'TaskNotFound':
      return fail(404, 'task_not_found', result.message)
    case 'TaskNotCancellable':
      return fail(409, 'task_not_cancellable', result.message)
    default:
      return assertNever(result)
  }
}

/** Queue a rejected publication again; the browser names the new task (R-TK-09). */
export async function retryTask(graphql: GraphqlClient, id: unknown, body: unknown): Promise<TaskView> {
  const { taskId } = parse(taskRef, { taskId: id })
  const { taskId: newTaskId } = parse(taskBody, body)
  const { result } = await graphql(RetryTaskDocument, { input: { taskId, newTaskId } })
  switch (result.__typename) {
    case 'Task':
      return toTaskView(result)
    case 'TaskNotFound':
      return fail(404, 'task_not_found', result.message)
    case 'TaskNotRetryable':
      return fail(409, 'task_not_retryable', result.message)
    case 'ValidationFailed':
      return fail(422, 'validation_failed', result.message, result.fields)
    case 'KeitaroFailure':
      return fail(502, 'keitaro_failure', result.message)
    case 'StreamBusy':
      return fail(409, 'stream_busy', result.message)
    case 'StreamNotFound':
      return fail(404, 'stream_not_found', result.message)
    case 'EmptyStream':
      return fail(422, 'empty_stream', result.message)
    case 'TaskKeyReused':
      return fail(409, 'task_key_reused', result.message)
    default:
      return assertNever(result)
  }
}
