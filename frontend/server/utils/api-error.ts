import type { ApiError, FieldRemark, StreamView } from '../../shared/types/api'

export class ApiFailure extends Error {
  constructor(readonly status: number, readonly body: ApiError) {
    super(body.message)
  }
}

export function fail(status: number, code: string, message: string, fields?: FieldRemark[]): never {
  throw new ApiFailure(status, fields ? { code, message, fields } : { code, message })
}

/** The stream moved on since the user saw it: answer with what it is now (R-CC-06). */
export function conflict(message: string, stream: StreamView): never {
  throw new ApiFailure(409, { code: 'stream_conflict', message, stream })
}

/** A new member of a union in the contract must break the build, not get lost. */
export function assertNever(value: never): never {
  throw new Error(`Unhandled variant: ${JSON.stringify(value)}`)
}
