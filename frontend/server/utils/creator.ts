import type { GraphqlClient } from './graphql'
import type { CampaignView } from './views'

export interface Option<T> {
  id: T
  name: string
}

export interface CreatorOptions {
  namePrefix: string
  domains: Option<number>[]
  groups: Option<number>[]
  trafficSources: Option<number>[]
  countries: Option<string>[]
}

/** Everything the creator form needs, in one answer (R-UX-02). */
export async function loadCreatorOptions(_graphql: GraphqlClient): Promise<CreatorOptions> {
  throw new Error('not implemented')
}

export async function searchOffers(_graphql: GraphqlClient, _query: unknown): Promise<Option<number>[]> {
  throw new Error('not implemented')
}

export async function createCampaign(_graphql: GraphqlClient, _body: unknown): Promise<CampaignView> {
  throw new Error('not implemented')
}
