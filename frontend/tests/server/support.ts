import type { TypedDocumentNode } from '@graphql-typed-document-node/core'
import { expect } from 'vitest'
import type { ApiError } from '../../shared/types/api'
import { ApiFailure } from '../../server/utils/api-error'
import type { GraphqlClient } from '../../server/utils/graphql'

export interface Call {
  operation: string
  variables: unknown
}

function operationName(document: TypedDocumentNode<unknown, unknown>): string {
  const definition = document.definitions.find(item => item.kind === 'OperationDefinition')
  return definition?.kind === 'OperationDefinition' ? (definition.name?.value ?? '') : ''
}

/** A backend that answers each operation with a prepared value and remembers what it was asked. */
export function fakeBackend(answers: Record<string, unknown>) {
  const calls: Call[] = []
  const graphql: GraphqlClient = async (document, variables) => {
    const operation = operationName(document as TypedDocumentNode<unknown, unknown>)
    calls.push({ operation, variables })
    if (!(operation in answers)) throw new Error(`unexpected operation ${operation}`)
    return answers[operation] as never
  }
  return { graphql, calls }
}

export async function refusal(action: Promise<unknown>): Promise<{ status: number, body: ApiError }> {
  const error = await action.then(
    () => { throw new Error('expected a refusal') },
    (caught: unknown) => caught,
  )
  expect(error).toBeInstanceOf(ApiFailure)
  const failure = error as ApiFailure
  return { status: failure.status, body: failure.body }
}

export const CAMPAIGN = { id: 'c-1', keitaroId: 93212, name: 'test_bulygin_au', alias: 'alias001', country: 'AU' }

export function offer(offerId: number, share: number, extra: Record<string, unknown> = {}) {
  return {
    offerId,
    name: `Offer ${offerId}`,
    share,
    pinned: false,
    state: 'ACTIVE',
    changed: false,
    published: { share, state: 'ACTIVE' },
    ...extra,
  }
}

export function stream(extra: Record<string, unknown> = {}) {
  return {
    __typename: 'Stream',
    id: 's-2',
    keitaroId: 564221,
    name: 'Flow 2',
    position: 2,
    kind: 'landings',
    dirty: false,
    version: 3,
    publishingTaskId: null,
    offers: [offer(1, 34), offer(2, 33), offer(3, 33)],
    ...extra,
  }
}

export const TASK_ID = '0b9d3c4e-6a55-4f0e-9d1f-2c1f6f3f8a10'

export function task(extra: Record<string, unknown> = {}) {
  return {
    __typename: 'Task',
    id: TASK_ID,
    kind: 'PUBLISH_STREAM',
    status: 'PENDING',
    attempts: 0,
    createdAt: '2026-11-17T12:00:00+00:00',
    startedAt: null,
    finishedAt: null,
    campaignId: 'c-1',
    streamId: 's-2',
    retryOf: null,
    refusal: null,
    steps: [{ name: 'queued', at: '2026-11-17T12:00:00+00:00', note: '' }],
    ...extra,
  }
}
