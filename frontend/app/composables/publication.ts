import type { TaskView } from '../../shared/types/api'

export interface FollowOptions {
  /** Ask for the task once. */
  load: (taskId: string) => Promise<TaskView>
  /** The first pause between questions, ms; every next one is twice as long. */
  pause?: number
  /** The longest pause, ms. */
  longest?: number
  /** How long to keep asking, ms. */
  patience?: number
  wait?: (ms: number) => Promise<void>
  /** Hear about every answer, to show how far the task went. */
  onUpdate?: (task: TaskView) => void
}

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/**
 * Ask about a task until nothing more will happen to it (R-UX-18).
 * A failed question is asked again: the task goes on whether or not the page hears about it.
 * Returns null when patience ran out — the task is still unfinished.
 */
export async function followTask(taskId: string, options: FollowOptions): Promise<TaskView | null> {
  const { load, pause = 100, longest = 1000, patience = 120_000, wait = sleep, onUpdate } = options
  // a short task is seen almost at once, a long one is asked about less and less often
  for (let waited = 0, next = pause; waited <= patience; waited += next, next = Math.min(next * 2, longest)) {
    try {
      const task = await load(taskId)
      onUpdate?.(task)
      if (task.finished) return task
    }
    catch {
      // the next question may get through
    }
    await wait(next)
  }
  return null
}
