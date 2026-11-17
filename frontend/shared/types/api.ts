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
  /** With `stream_conflict`: the stream as it is stored now (R-CC-06). */
  stream?: StreamView
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
  /** The number of the stream's last write; every action sends it back (R-CC-06). */
  version: number
  /** The unfinished task that publishes the stream; while it is set, the stream is locked (R-UX-18). */
  publishingTaskId: string | null
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

export type TaskStatus = 'pending' | 'running' | 'succeeded' | 'rejected' | 'cancelled'

export interface TaskStepView {
  name: string
  at: string
  note: string
}

/** A change of the tracker that is carried out apart from the request (R-TK-05). */
export interface TaskView {
  id: string
  kind: 'publish_stream' | 'create_campaign'
  status: TaskStatus
  /** Nothing more will happen to the task. */
  finished: boolean
  attempts: number
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  campaignId: string | null
  streamId: string | null
  /** Why the task was rejected, in words for the user. */
  refusal: string | null
  steps: TaskStepView[]
}
