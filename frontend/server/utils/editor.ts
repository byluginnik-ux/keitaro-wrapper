import type { CampaignView, EditorScreen, StreamView } from '../../shared/types/api'
import type { StreamOutcomeFragment } from '../graphql/operations'
import {
  AddOfferDocument,
  BringBackOfferDocument,
  CampaignsDocument,
  CancelDraftDocument,
  EditorScreenDocument,
  FetchStreamsDocument,
  PinShareDocument,
  PushStreamDocument,
  RemoveOfferDocument,
  TrackerUrlDocument,
  UnpinShareDocument,
} from '../graphql/operations'
import { assertNever, fail } from './api-error'
import type { GraphqlClient } from './graphql'
import { fetchInput, offerBody, offerRef, parse, shareBody, streamRef } from './schemas'
import { toCampaignView, toStreamView } from './views'

export type StreamAction = 'add' | 'remove' | 'restore' | 'pin' | 'unpin' | 'cancel' | 'push'

export interface StreamActionInput {
  streamId: unknown
  offerId?: unknown
  body?: unknown
}

/** Where the tracker lives: links into its admin panel are built from this. */
export async function trackerUrl(graphql: GraphqlClient): Promise<string> {
  return (await graphql(TrackerUrlDocument, {})).serviceInfo.trackerUrl
}

export async function listCampaigns(graphql: GraphqlClient): Promise<CampaignView[]> {
  const data = await graphql(CampaignsDocument, {})
  return data.campaigns.map(campaign => toCampaignView(campaign, data.serviceInfo.trackerUrl))
}

/** The editor screen in one answer: the campaign and its streams as stored. */
export async function loadEditor(graphql: GraphqlClient, campaignId: unknown): Promise<EditorScreen> {
  const { streamId: id } = parse(streamRef, { streamId: campaignId })
  const data = await graphql(EditorScreenDocument, { id })
  if (data.campaign === null) fail(404, 'campaign_not_found', 'Такой кампании у нас нет')
  return {
    campaign: toCampaignView(data.campaign, data.serviceInfo.trackerUrl),
    streams: data.streams.map(toStreamView),
  }
}

/** Load streams from the tracker by the campaign's tracker ID. */
export async function fetchStreams(graphql: GraphqlClient, body: unknown): Promise<EditorScreen> {
  const { keitaroId } = parse(fetchInput, body)
  const { fetchStreams: result } = await graphql(FetchStreamsDocument, { keitaroId })
  switch (result.__typename) {
    case 'StreamsFetched':
      return {
        campaign: toCampaignView(result.campaign, await trackerUrl(graphql)),
        streams: result.streams.map(toStreamView),
      }
    case 'DraftNotPublished':
      return fail(409, 'draft_not_published', result.message)
    case 'CampaignNotFound':
      return fail(404, 'campaign_not_found', result.message)
    case 'KeitaroFailure':
      return fail(502, 'keitaro_failure', result.message)
    default:
      return assertNever(result)
  }
}

function unwrap(result: StreamOutcomeFragment): StreamView {
  switch (result.__typename) {
    case 'Stream':
      return toStreamView(result)
    case 'StreamConflict':
      return fail(409, 'stream_conflict', result.message)
    case 'StreamNotFound':
      return fail(404, 'stream_not_found', result.message)
    case 'OfferNotFound':
      return fail(404, 'offer_not_found', result.message)
    case 'OfferAlreadyInStream':
      return fail(409, 'offer_already_in_stream', result.message)
    case 'ShareOverflow':
      return fail(422, 'share_overflow', result.message)
    case 'EmptyStream':
      return fail(422, 'empty_stream', result.message)
    case 'ValidationFailed':
      return fail(422, 'validation_failed', result.message, result.fields)
    case 'KeitaroFailure':
      return fail(502, 'keitaro_failure', result.message)
    default:
      return assertNever(result)
  }
}

const OFFER_ACTIONS = {
  remove: RemoveOfferDocument,
  restore: BringBackOfferDocument,
  unpin: UnpinShareDocument,
} as const
const STREAM_ACTIONS = { cancel: CancelDraftDocument, push: PushStreamDocument } as const

/** Run one action of the editor; every action answers with the whole stream. */
export async function runStreamAction(
  graphql: GraphqlClient,
  action: StreamAction,
  input: StreamActionInput,
): Promise<StreamView> {
  switch (action) {
    case 'add': {
      const { streamId } = parse(streamRef, input)
      const { offerId } = parse(offerBody, input.body)
      return unwrap((await graphql(AddOfferDocument, { input: { streamId, offerId } })).result)
    }
    case 'pin': {
      const reference = parse(offerRef, input)
      const { share } = parse(shareBody, input.body)
      return unwrap((await graphql(PinShareDocument, { input: { ...reference, share } })).result)
    }
    case 'remove':
    case 'restore':
    case 'unpin':
      return unwrap((await graphql(OFFER_ACTIONS[action], { input: parse(offerRef, input) })).result)
    case 'cancel':
    case 'push':
      return unwrap((await graphql(STREAM_ACTIONS[action], parse(streamRef, input))).result)
    default:
      return assertNever(action)
  }
}
