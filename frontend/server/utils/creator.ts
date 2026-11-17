import type { CreatorOptions, Option, TaskView } from '../../shared/types/api'
import { CreateCampaignDocument, CreatorOptionsDocument, SearchOffersDocument } from '../graphql/operations'
import { assertNever, fail } from './api-error'
import type { GraphqlClient } from './graphql'
import { campaignInput, offerSearch, parse } from './schemas'
import { toTaskView } from './views'

const OFFER_LIMIT = 20

/** Everything the creator form needs, in one answer (R-UX-02). */
export async function loadCreatorOptions(graphql: GraphqlClient): Promise<CreatorOptions> {
  const data = await graphql(CreatorOptionsDocument, {})
  return {
    namePrefix: data.serviceInfo.campaignNamePrefix,
    domains: data.domains,
    groups: data.groups,
    trafficSources: data.trafficSources,
    countries: data.countries.map(country => ({ id: country.code, name: country.name })),
  }
}

export async function searchOffers(graphql: GraphqlClient, query: unknown): Promise<Option<number>[]> {
  const { search } = parse(offerSearch, query)
  const data = await graphql(SearchOffersDocument, { search, limit: OFFER_LIMIT })
  return data.offers
}

/** Queue the creation of a campaign; the answer is the task to follow (R-CR-13). */
export async function createCampaign(graphql: GraphqlClient, body: unknown): Promise<TaskView> {
  const input = parse(campaignInput, body)
  const { createCampaign: result } = await graphql(CreateCampaignDocument, { input })
  switch (result.__typename) {
    case 'Task':
      return toTaskView(result)
    case 'ValidationFailed':
      return fail(422, 'validation_failed', result.message, result.fields)
    case 'KeitaroFailure':
      return fail(502, 'keitaro_failure', result.message)
    case 'TaskKeyReused':
      return fail(409, 'task_key_reused', result.message)
    default:
      return assertNever(result)
  }
}
