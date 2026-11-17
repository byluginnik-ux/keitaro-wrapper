import type { CreatorOptions, Option, TaskView } from '../../shared/types/api'
import { CreatorOptionsDocument, SearchOffersDocument } from '../graphql/operations'
import { fail } from './api-error'
import type { GraphqlClient } from './graphql'
import { offerSearch, parse } from './schemas'

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
export async function createCampaign(_graphql: GraphqlClient, _body: unknown): Promise<TaskView> {
  return fail(501, 'not_implemented', 'Создание кампании переводится на задачи')
}
