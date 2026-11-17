import type { OfferState } from '@keitaro-wrapper/contracts'
import type { CampaignView, OfferView, StreamView, TaskStatus, TaskView } from '../../shared/types/api'
import type { CampaignFieldsFragment, StreamFieldsFragment, TaskFieldsFragment } from '../graphql/operations'

const REMOVED: OfferState = 'REMOVED'

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
    version: stream.version,
    publishingTaskId: stream.publishingTaskId ?? null,
    changes: offers.filter(offer => offer.changed).length,
    total: offers.reduce((sum, offer) => sum + offer.share, 0),
    offers,
  }
}

const FINISHED: TaskStatus[] = ['succeeded', 'rejected', 'cancelled']

export function toTaskView(task: TaskFieldsFragment): TaskView {
  const status = task.status.toLowerCase() as TaskStatus
  return {
    id: task.id,
    kind: task.kind.toLowerCase() as TaskView['kind'],
    status,
    finished: FINISHED.includes(status),
    attempts: task.attempts,
    createdAt: task.createdAt,
    startedAt: task.startedAt ?? null,
    finishedAt: task.finishedAt ?? null,
    campaignId: task.campaignId ?? null,
    streamId: task.streamId ?? null,
    refusal: task.refusal?.message ?? null,
    steps: task.steps.map(step => ({ name: step.name, at: step.at, note: step.note })),
  }
}
