import type { CampaignFieldsFragment, StreamFieldsFragment } from '../graphql/operations'

export interface CampaignView {
  id: string
  keitaroId: number
  name: string
  alias: string
  country: string | null
  /** The campaign in the tracker's own admin panel. */
  trackerLink: string
}

export interface OfferView {
  offerId: number
  name: string
  share: number
  pinned: boolean
  removed: boolean
  /** Never published: cancelling the draft makes it disappear. */
  isNew: boolean
  changed: boolean
  publishedShare: number | null
}

export interface StreamView {
  id: string
  keitaroId: number
  name: string
  position: number
  /** False for a redirect stream: it is shown without contents. */
  acceptsOffers: boolean
  dirty: boolean
  /** How many offers a publication would change. */
  changes: number
  /** Sum of the shares of active offers, as stored. */
  total: number
  offers: OfferView[]
}

export function toCampaignView(_campaign: CampaignFieldsFragment, _trackerUrl: string): CampaignView {
  throw new Error('not implemented')
}

export function toStreamView(_stream: StreamFieldsFragment): StreamView {
  throw new Error('not implemented')
}
