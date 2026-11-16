import type { H3Event } from 'h3'
import { ApiFailure } from './api-error'
import type { GraphqlClient, GraphqlResponse } from './graphql'
import { createGraphqlClient } from './graphql'

/** Wire a screen function to HTTP: give it the backend client, turn its refusals into statuses. */
export function defineApiHandler<T>(run: (event: H3Event, graphql: GraphqlClient) => Promise<T>) {
  return defineEventHandler(async (event) => {
    const { backendGraphqlUrl } = useRuntimeConfig(event)
    const graphql = createGraphqlClient(backendGraphqlUrl, (url, body) =>
      $fetch<GraphqlResponse>(url, { method: 'POST', body }),
    )
    try {
      return await run(event, graphql)
    }
    catch (error) {
      if (!(error instanceof ApiFailure)) throw error
      throw createError({ statusCode: error.status, statusMessage: error.body.code, data: error.body })
    }
  })
}
