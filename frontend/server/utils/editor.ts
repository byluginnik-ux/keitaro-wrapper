import type { GraphqlClient } from './graphql'
import type { CampaignView, StreamView } from './views'

export interface EditorScreen {
  campaign: CampaignView
  streams: StreamView[]
}

export type StreamAction = 'add' | 'remove' | 'restore' | 'pin' | 'unpin' | 'cancel' | 'push'

export interface StreamActionInput {
  streamId: unknown
  offerId?: unknown
  body?: unknown
}

export async function listCampaigns(_graphql: GraphqlClient): Promise<CampaignView[]> {
  throw new Error('not implemented')
}

/** The editor screen in one answer: the campaign and its streams as stored. */
export async function loadEditor(_graphql: GraphqlClient, _campaignId: unknown): Promise<EditorScreen> {
  throw new Error('not implemented')
}

/** Load streams from the tracker by the campaign's tracker ID. */
export async function fetchStreams(_graphql: GraphqlClient, _body: unknown): Promise<EditorScreen> {
  throw new Error('not implemented')
}

/** Run one action of the editor; every action answers with the whole stream. */
export async function runStreamAction(
  _graphql: GraphqlClient,
  _action: StreamAction,
  _input: StreamActionInput,
): Promise<StreamView> {
  throw new Error('not implemented')
}
