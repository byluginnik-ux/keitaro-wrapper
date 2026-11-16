import type { ApiError, FieldRemark } from '../../shared/types/api'

export class ApiFailure extends Error {
  constructor(readonly status: number, readonly body: ApiError) {
    super(body.message)
  }
}

export function fail(status: number, code: string, message: string, fields?: FieldRemark[]): never {
  throw new ApiFailure(status, fields ? { code, message, fields } : { code, message })
}

/** A new member of a union in the contract must break the build, not get lost. */
export function assertNever(value: never): never {
  throw new Error(`Unhandled variant: ${JSON.stringify(value)}`)
}
