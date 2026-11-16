/** What the BFF answers with: the models of the screens and the one shape of a refusal. */

export interface FieldRemark {
  field: string
  message: string
}

/** The only shape of a refusal the browser ever sees (R-ARCH-05). */
export interface ApiError {
  code: string
  message: string
  fields?: FieldRemark[]
}

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

export interface EditorScreen {
  campaign: CampaignView
  streams: StreamView[]
}
