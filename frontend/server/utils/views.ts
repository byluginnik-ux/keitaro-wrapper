import type { OfferState } from '@keitaro-wrapper/contracts'
import type { CampaignFieldsFragment, StreamFieldsFragment } from '../graphql/operations'

const REMOVED: OfferState = 'REMOVED'

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

const OFFERS_KIND = 'landings'

export function toCampaignView(campaign: CampaignFieldsFragment, trackerUrl: string): CampaignView {
  return {
    id: campaign.id,
    keitaroId: campaign.keitaroId,
    name: campaign.name,
    alias: campaign.alias,
    country: campaign.country,
    trackerLink: `${trackerUrl}/admin/#!/campaigns/${campaign.keitaroId}`,
  }
}

export function toStreamView(stream: StreamFieldsFragment): StreamView {
  const offers = stream.offers.map((offer): OfferView => ({
    offerId: offer.offerId,
    name: offer.name,
    share: offer.share,
    pinned: offer.pinned,
    removed: offer.state === REMOVED,
    isNew: offer.published === null,
    changed: offer.changed,
    publishedShare: offer.published?.share ?? null,
  }))
  return {
    id: stream.id,
    keitaroId: stream.keitaroId,
    name: stream.name,
    position: stream.position,
    acceptsOffers: stream.kind === OFFERS_KIND,
    dirty: stream.dirty,
    changes: offers.filter(offer => offer.changed).length,
    total: offers.reduce((sum, offer) => sum + offer.share, 0),
    offers,
  }
}
