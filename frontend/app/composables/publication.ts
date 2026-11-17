import type { TaskView } from '../../shared/types/api'

export interface FollowOptions {
  /** Ask for the task once. */
  load: (taskId: string) => Promise<TaskView>
  /** Pause between questions, ms. */
  pause?: number
  /** How long to keep asking, ms. */
  patience?: number
  wait?: (ms: number) => Promise<void>
}

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/**
 * Ask about a task until nothing more will happen to it (R-UX-18).
 * A failed question is asked again: the task goes on whether or not the page hears about it.
 * Returns null when patience ran out — the task is still unfinished.
 */
export async function followTask(taskId: string, options: FollowOptions): Promise<TaskView | null> {
  const { load, pause = 400, patience = 120_000, wait = sleep } = options
  for (let waited = 0; waited <= patience; waited += pause) {
    try {
      const task = await load(taskId)
      if (task.finished) return task
    }
    catch {
      // the next question may get through
    }
    await wait(pause)
  }
  return null
}
