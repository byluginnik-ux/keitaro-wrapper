import type { CampaignView, CreatorOptions, Option } from '../../shared/types/api'
import { CreateCampaignDocument, CreatorOptionsDocument, SearchOffersDocument } from '../graphql/operations'
import { assertNever, fail } from './api-error'
import { trackerUrl } from './editor'
import type { GraphqlClient } from './graphql'
import { campaignInput, offerSearch, parse } from './schemas'
import { toCampaignView } from './views'

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

export async function createCampaign(graphql: GraphqlClient, body: unknown): Promise<CampaignView> {
  const input = parse(campaignInput, body)
  const { createCampaign: result } = await graphql(CreateCampaignDocument, { input })
  switch (result.__typename) {
    case 'Campaign':
      return toCampaignView(result, await trackerUrl(graphql))
    case 'ValidationFailed':
      return fail(422, 'validation_failed', result.message, result.fields)
    case 'KeitaroFailure':
      return fail(502, 'keitaro_failure', result.message)
    default:
      return assertNever(result)
  }
}
