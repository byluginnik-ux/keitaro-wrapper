import type { TypedDocumentNode } from '@graphql-typed-document-node/core'
import { print } from 'graphql'
import { fail } from './api-error'

export type GraphqlClient = <TData, TVariables>(
  document: TypedDocumentNode<TData, TVariables>,
  variables: TVariables,
) => Promise<TData>

export interface GraphqlResponse {
  data?: unknown
  errors?: Array<{ message: string, extensions?: { code?: string } }>
}

export type Post = (url: string, body: { query: string, variables: unknown }) => Promise<GraphqlResponse>

const UNAVAILABLE = 'Сервис временно недоступен. Повторите попытку позже.'

/** One thin client: a typed document and variables in, data out; no cache, no state. */
export function createGraphqlClient(url: string, post: Post): GraphqlClient {
  return async (document, variables) => {
    let response: GraphqlResponse
    try {
      response = await post(url, { query: print(document), variables })
    }
    catch {
      // the cause carries the backend address; it stays on the server (R-ARCH-04)
      fail(502, 'backend_unavailable', UNAVAILABLE)
    }
    const error = response.errors?.[0]
    if (error?.extensions?.code === 'keitaro_error') fail(502, 'keitaro_failure', error.message)
    if (error || response.data === undefined || response.data === null) {
      fail(502, 'backend_unavailable', UNAVAILABLE)
    }
    return response.data as never
  }
}
