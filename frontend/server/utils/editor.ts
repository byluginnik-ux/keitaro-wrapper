import type { CampaignView, EditorScreen, StreamView, TaskView } from '../../shared/types/api'
import type { StreamOutcomeFragment } from '../graphql/operations'
import {
  AddOfferDocument,
  BringBackOfferDocument,
  CampaignsDocument,
  CancelDraftDocument,
  EditorScreenDocument,
  FetchStreamsDocument,
  PinShareDocument,
  PublishStreamDocument,
  RemoveOfferDocument,
  TaskStateDocument,
  TrackerUrlDocument,
  UnpinShareDocument,
} from '../graphql/operations'
import { assertNever, conflict, fail } from './api-error'
import type { GraphqlClient } from './graphql'
import { fetchInput, offerBody, offerRef, parse, shareBody, streamRef, taskBody, taskRef } from './schemas'
import { toCampaignView, toStreamView, toTaskView } from './views'

export type StreamAction = 'add' | 'remove' | 'restore' | 'pin' | 'unpin' | 'cancel'

export interface StreamActionInput {
  streamId: unknown
  offerId?: unknown
  /** The version of the stream on the user's screen, from the query string. */
  version?: unknown
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
    case 'StreamBusy':
      return fail(409, 'stream_busy', result.message)
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
      return conflict(result.message, toStreamView(result.stream))
    case 'StreamBusy':
      return fail(409, 'stream_busy', result.message)
    case 'StreamNotFound':
      return fail(404, 'stream_not_found', result.message)
    case 'OfferNotFound':
      return fail(404, 'offer_not_found', result.message)
    case 'OfferAlreadyInStream':
      return fail(409, 'offer_already_in_stream', result.message)
    case 'ShareOverflow':
      return fail(422, 'share_overflow', result.message)
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

/** Run one action of the editor; every action answers with the whole stream. */
export async function runStreamAction(
  graphql: GraphqlClient,
  action: StreamAction,
  input: StreamActionInput,
): Promise<StreamView> {
  switch (action) {
    case 'add': {
      const { streamId, version } = parse(streamRef, input)
      const { offerId } = parse(offerBody, input.body)
      const variables = { input: { streamId, offerId, expectedVersion: version } }
      return unwrap((await graphql(AddOfferDocument, variables)).result)
    }
    case 'pin': {
      const { version, ...reference } = parse(offerRef, input)
      const { share } = parse(shareBody, input.body)
      const variables = { input: { ...reference, share, expectedVersion: version } }
      return unwrap((await graphql(PinShareDocument, variables)).result)
    }
    case 'remove':
    case 'restore':
    case 'unpin':
    {
      const { version, ...reference } = parse(offerRef, input)
      const variables = { input: { ...reference, expectedVersion: version } }
      return unwrap((await graphql(OFFER_ACTIONS[action], variables)).result)
    }
    case 'cancel': {
      const { streamId, version } = parse(streamRef, input)
      const variables = { streamId, expectedVersion: version }
      return unwrap((await graphql(CancelDraftDocument, variables)).result)
    }
    default:
      return assertNever(action)
  }
}

/** Queue the publication of a stream; the answer is the task to follow (R-ED-20, R-TK-04). */
export async function publishStream(graphql: GraphqlClient, input: StreamActionInput): Promise<TaskView> {
  const { streamId, version } = parse(streamRef, input)
  const { taskId } = parse(taskBody, input.body)
  const variables = { input: { streamId, taskId, expectedVersion: version } }
  const { result } = await graphql(PublishStreamDocument, variables)
  switch (result.__typename) {
    case 'Task':
      return toTaskView(result)
    case 'StreamConflict':
      return conflict(result.message, toStreamView(result.stream))
    case 'StreamBusy':
      return fail(409, 'stream_busy', result.message)
    case 'StreamNotFound':
      return fail(404, 'stream_not_found', result.message)
    case 'EmptyStream':
      return fail(422, 'empty_stream', result.message)
    case 'TaskKeyReused':
      return fail(409, 'task_key_reused', result.message)
    default:
      return assertNever(result)
  }
}

/** How a task is doing (R-TK-05). */
export async function loadTask(graphql: GraphqlClient, id: unknown): Promise<TaskView> {
  const { taskId } = parse(taskRef, { taskId: id })
  const { task } = await graphql(TaskStateDocument, { id: taskId })
  if (task === null) fail(404, 'task_not_found', 'Такой задачи нет')
  return toTaskView(task)
}
