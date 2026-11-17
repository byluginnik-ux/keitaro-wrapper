import type { TaskView, TasksScreen } from '../../shared/types/api'
import { fail } from './api-error'
import type { GraphqlClient } from './graphql'

const PENDING = 'Страница «Задачи» ещё не готова'

/** The "Tasks" page in one answer: the state of the queue and the latest tasks (R-UX-30). */
export async function loadTasks(_graphql: GraphqlClient, _query: unknown): Promise<TasksScreen> {
  return fail(501, 'not_implemented', PENDING)
}

/** Take back a task nobody has started yet (R-TK-08). */
export async function cancelTask(_graphql: GraphqlClient, _id: unknown): Promise<TaskView> {
  return fail(501, 'not_implemented', PENDING)
}

/** Queue a rejected publication again; the browser names the new task (R-TK-09). */
export async function retryTask(_graphql: GraphqlClient, _id: unknown, _body: unknown): Promise<TaskView> {
  return fail(501, 'not_implemented', PENDING)
}
