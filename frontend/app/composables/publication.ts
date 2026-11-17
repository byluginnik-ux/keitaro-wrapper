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

/**
 * Ask about a task until nothing more will happen to it (R-UX-18).
 * A failed question is asked again: the task goes on whether or not the page hears about it.
 * Returns null when patience ran out — the task is still unfinished.
 */
export async function followTask(_taskId: string, _options: FollowOptions): Promise<TaskView | null> {
  return null
}
