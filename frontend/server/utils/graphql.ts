import type { TypedDocumentNode } from '@graphql-typed-document-node/core'

export type GraphqlClient = <TData, TVariables>(
  document: TypedDocumentNode<TData, TVariables>,
  variables: TVariables,
) => Promise<TData>

export interface GraphqlResponse {
  data?: unknown
  errors?: Array<{ message: string, extensions?: { code?: string } }>
}

export type Post = (url: string, body: { query: string, variables: unknown }) => Promise<GraphqlResponse>

/** One thin client: a typed document and variables in, data out; no cache, no state. */
export function createGraphqlClient(_url: string, _post: Post): GraphqlClient {
  throw new Error('not implemented')
}
