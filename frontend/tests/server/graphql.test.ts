import { describe, expect, it } from 'vitest'
import { CampaignsDocument, EditorScreenDocument } from '../../server/graphql/operations'
import type { GraphqlResponse } from '../../server/utils/graphql'
import { createGraphqlClient } from '../../server/utils/graphql'
import { refusal } from './support'

function client(answer: GraphqlResponse | Error) {
  const sent: Array<{ url: string, body: { query: string, variables: unknown } }> = []
  const graphql = createGraphqlClient('http://backend:8000/graphql', async (url, body) => {
    sent.push({ url, body })
    if (answer instanceof Error) throw answer
    return answer
  })
  return { graphql, sent }
}

describe('graphql client', () => {
  it('sends the document as text with its variables and returns the data', async () => {
    const { graphql, sent } = client({ data: { campaign: null, streams: [], serviceInfo: { trackerUrl: 't' } } })

    const data = await graphql(EditorScreenDocument, { id: 'c-1' })

    expect(data.streams).toEqual([])
    expect(sent[0]?.url).toBe('http://backend:8000/graphql')
    expect(sent[0]?.body.query).toContain('query EditorScreen($id: ID!)')
    expect(sent[0]?.body.query).toContain('fragment StreamFields on Stream')
    expect(sent[0]?.body.variables).toEqual({ id: 'c-1' })
  })

  it('reports an unreachable backend without its address (R-ARCH-04)', async () => {
    const { graphql } = client(new Error('connect ECONNREFUSED http://backend:8000/graphql'))

    const { status, body } = await refusal(graphql(CampaignsDocument, {}))

    expect(status).toBe(502)
    expect(body.code).toBe('backend_unavailable')
    expect(JSON.stringify(body)).not.toContain('backend:8000')
  })

  it('passes a tracker failure on with the tracker\'s own words', async () => {
    const { graphql } = client({
      data: null,
      errors: [{ message: 'Keitaro: invalid api key', extensions: { code: 'keitaro_error' } }],
    })

    const { status, body } = await refusal(graphql(CampaignsDocument, {}))

    expect(status).toBe(502)
    expect(body).toEqual({ code: 'keitaro_failure', message: 'Keitaro: invalid api key' })
  })

  it('hides any other backend error behind one message', async () => {
    const { graphql } = client({
      errors: [{ message: 'Cannot query field "x" on type "Query"' }],
    })

    const { body } = await refusal(graphql(CampaignsDocument, {}))

    expect(body.code).toBe('backend_unavailable')
    expect(body.message).not.toContain('Query')
  })

  it('treats an answer without data as a failure', async () => {
    const { graphql } = client({})

    const { body } = await refusal(graphql(CampaignsDocument, {}))

    expect(body.code).toBe('backend_unavailable')
  })
})
