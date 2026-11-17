import { describe, expect, it } from 'vitest'
import { fetchStreams, listCampaigns, loadEditor, loadTask, publishStream, runStreamAction } from '../../server/utils/editor'
import { CAMPAIGN, TASK_ID, fakeBackend, offer, refusal, stream, task } from './support'

const INFO = { trackerUrl: 'https://tracker.test' }
const LINK = 'https://tracker.test/admin/#!/campaigns/93212'

describe('campaign list', () => {
  it('lists campaigns with links into the tracker', async () => {
    const { graphql } = fakeBackend({ Campaigns: { serviceInfo: INFO, campaigns: [CAMPAIGN] } })

    expect(await listCampaigns(graphql)).toEqual([{ ...CAMPAIGN, trackerLink: LINK }])
  })
})

describe('editor screen', () => {
  it('turns streams into what the page shows (R-UX-10, R-UX-12, R-UX-13)', async () => {
    const draft = stream({
      dirty: true,
      offers: [
        offer(1, 25, { changed: true, published: { share: 34, state: 'ACTIVE' } }),
        offer(2, 0, { state: 'REMOVED', changed: true, published: { share: 33, state: 'ACTIVE' } }),
        offer(3, 50, { pinned: true, changed: true, published: { share: 33, state: 'ACTIVE' } }),
        offer(4, 25, { changed: true, published: null }),
      ],
    })
    const redirect = stream({ id: 's-1', keitaroId: 564220, name: 'Flow 1', position: 1, kind: 'redirect', offers: [] })
    const { graphql, calls } = fakeBackend({
      EditorScreen: { serviceInfo: INFO, campaign: CAMPAIGN, streams: [redirect, draft] },
    })

    const screen = await loadEditor(graphql, 'c-1')

    expect(calls).toEqual([{ operation: 'EditorScreen', variables: { id: 'c-1' } }])
    expect(screen.campaign).toEqual({ ...CAMPAIGN, trackerLink: LINK })
    expect(screen.streams[0]).toEqual({
      id: 's-1',
      keitaroId: 564220,
      name: 'Flow 1',
      position: 1,
      acceptsOffers: false,
      dirty: false,
      version: 3,
      publishingTaskId: null,
      changes: 0,
      total: 0,
      offers: [],
    })
    expect(screen.streams[1]).toMatchObject({ acceptsOffers: true, dirty: true, changes: 4, total: 100 })
    expect(screen.streams[1]?.offers).toEqual([
      { offerId: 1, name: 'Offer 1', share: 25, pinned: false, removed: false, isNew: false, changed: true, publishedShare: 34 },
      { offerId: 2, name: 'Offer 2', share: 0, pinned: false, removed: true, isNew: false, changed: true, publishedShare: 33 },
      { offerId: 3, name: 'Offer 3', share: 50, pinned: true, removed: false, isNew: false, changed: true, publishedShare: 33 },
      { offerId: 4, name: 'Offer 4', share: 25, pinned: false, removed: false, isNew: true, changed: true, publishedShare: null },
    ])
  })

  it('answers 404 for a campaign we do not have', async () => {
    const { graphql } = fakeBackend({ EditorScreen: { serviceInfo: INFO, campaign: null, streams: [] } })

    const { status, body } = await refusal(loadEditor(graphql, 'nope'))

    expect(status).toBe(404)
    expect(body.code).toBe('campaign_not_found')
  })
})

describe('fetch streams', () => {
  it('loads a campaign by its tracker ID (R-ED-07)', async () => {
    const { graphql, calls } = fakeBackend({
      FetchStreams: { fetchStreams: { __typename: 'StreamsFetched', campaign: CAMPAIGN, streams: [stream()] } },
      TrackerUrl: { serviceInfo: INFO },
    })

    const screen = await fetchStreams(graphql, { keitaroId: '93212' })

    expect(calls[0]).toEqual({ operation: 'FetchStreams', variables: { keitaroId: 93212 } })
    expect(screen.campaign.trackerLink).toBe(LINK)
    expect(screen.streams[0]?.offers.map(item => item.share)).toEqual([34, 33, 33])
  })

  it.each([
    ['DraftNotPublished', 409, 'draft_not_published'],
    ['CampaignNotFound', 404, 'campaign_not_found'],
    ['KeitaroFailure', 502, 'keitaro_failure'],
  ])('maps %s to %i', async (typename, status, code) => {
    const { graphql } = fakeBackend({
      FetchStreams: { fetchStreams: { __typename: typename, message: 'почему' } },
    })

    expect(await refusal(fetchStreams(graphql, { keitaroId: 1 }))).toEqual({
      status,
      body: { code, message: 'почему' },
    })
  })

  it.each([[{}], [{ keitaroId: 'abc' }], [{ keitaroId: -1 }], [{ keitaroId: 1.5 }]])(
    'rejects %j without asking the backend',
    async (body) => {
      const { graphql, calls } = fakeBackend({})

      expect((await refusal(fetchStreams(graphql, body))).status).toBe(400)
      expect(calls).toHaveLength(0)
    },
  )
})

describe('stream actions', () => {
  const answer = { result: stream({ dirty: true }) }

  it.each([
    ['add', 'AddOffer', { streamId: 's-2', body: { offerId: 4 } }, { input: { streamId: 's-2', offerId: 4 } }],
    ['remove', 'RemoveOffer', { streamId: 's-2', offerId: '4' }, { input: { streamId: 's-2', offerId: 4 } }],
    ['restore', 'BringBackOffer', { streamId: 's-2', offerId: '4' }, { input: { streamId: 's-2', offerId: 4 } }],
    ['pin', 'PinShare', { streamId: 's-2', offerId: '4', body: { share: 25 } }, { input: { streamId: 's-2', offerId: 4, share: 25 } }],
    ['unpin', 'UnpinShare', { streamId: 's-2', offerId: '4' }, { input: { streamId: 's-2', offerId: 4 } }],
  ] as const)('%s calls %s with the version the user saw and returns the whole stream (R-CC-06)', async (action, operation, input, variables) => {
    const { graphql, calls } = fakeBackend({ [operation]: answer })

    const view = await runStreamAction(graphql, action, { ...input, version: '3' })

    expect(calls).toEqual([{ operation, variables: { input: { ...variables.input, expectedVersion: 3 } } }])
    expect(view).toMatchObject({ id: 's-2', dirty: true, total: 100, version: 3 })
  })

  it('cancel calls CancelDraft with the version the user saw (R-CC-06)', async () => {
    const { graphql, calls } = fakeBackend({ CancelDraft: answer })

    await runStreamAction(graphql, 'cancel', { streamId: 's-2', version: '3' })

    expect(calls).toEqual([{ operation: 'CancelDraft', variables: { streamId: 's-2', expectedVersion: 3 } }])
  })

  it('acts on what is stored when no version came', async () => {
    const { graphql, calls } = fakeBackend({ CancelDraft: answer })

    await runStreamAction(graphql, 'cancel', { streamId: 's-2' })

    expect(calls[0]?.variables).toEqual({ streamId: 's-2' })
  })

  it('answers a conflict with the stream as it is now (R-CC-06)', async () => {
    const current = stream({ dirty: true, version: 4, offers: [offer(1, 50), offer(3, 50)] })
    const { graphql } = fakeBackend({
      AddOffer: { result: { __typename: 'StreamConflict', message: 'Поток изменён', stream: current } },
    })

    const { status, body } = await refusal(
      runStreamAction(graphql, 'add', { streamId: 's-2', version: 3, body: { offerId: 4 } }),
    )

    expect(status).toBe(409)
    expect(body).toMatchObject({ code: 'stream_conflict', message: 'Поток изменён' })
    expect(body.stream).toMatchObject({ id: 's-2', version: 4, total: 100 })
    expect(body.stream?.offers.map(item => item.offerId)).toEqual([1, 3])
  })

  it.each([
    ['StreamNotFound', 404, 'stream_not_found'],
    ['OfferNotFound', 404, 'offer_not_found'],
    ['OfferAlreadyInStream', 409, 'offer_already_in_stream'],
    ['ShareOverflow', 422, 'share_overflow'],
    ['StreamBusy', 409, 'stream_busy'],
    ['KeitaroFailure', 502, 'keitaro_failure'],
  ])('maps %s to %i', async (typename, status, code) => {
    const { graphql } = fakeBackend({ CancelDraft: { result: { __typename: typename, message: 'почему' } } })

    expect(await refusal(runStreamAction(graphql, 'cancel', { streamId: 's-2' }))).toEqual({
      status,
      body: { code, message: 'почему' },
    })
  })

  it('passes field remarks of a refused share on', async () => {
    const fields = [{ field: 'share', message: 'Доля — целое число от 1 до 100' }]
    const { graphql } = fakeBackend({
      PinShare: { result: { __typename: 'ValidationFailed', message: 'Проверьте поля: share', fields } },
    })

    const { status, body } = await refusal(
      runStreamAction(graphql, 'pin', { streamId: 's-2', offerId: 4, body: { share: 0 } }),
    )

    expect(status).toBe(422)
    expect(body.fields).toEqual(fields)
  })

  it.each([
    ['add', { streamId: 's-2', body: {} }],
    ['add', { streamId: 's-2', body: { offerId: 'four' } }],
    ['pin', { streamId: 's-2', offerId: 4, body: { share: '25%' } }],
    ['remove', { streamId: 's-2', offerId: 'x' }],
    ['cancel', { streamId: '' }],
    ['cancel', { streamId: 's-2', version: 'latest' }],
  ] as const)('rejects malformed %s %j without asking the backend', async (action, input) => {
    const { graphql, calls } = fakeBackend({})

    const { status, body } = await refusal(runStreamAction(graphql, action, input))

    expect(status).toBe(400)
    expect(body.code).toBe('invalid_input')
    expect(calls).toHaveLength(0)
  })

  it('leaves the rules of shares to the backend (R-ARCH-05)', async () => {
    const { graphql, calls } = fakeBackend({ PinShare: answer })

    await runStreamAction(graphql, 'pin', { streamId: 's-2', offerId: 4, body: { share: 250 } })

    expect(calls[0]?.variables).toMatchObject({ input: { streamId: 's-2', offerId: 4, share: 250 } })
  })
})

describe('publication', () => {
  const queued = {
    id: TASK_ID,
    kind: 'publish_stream',
    status: 'pending',
    finished: false,
    attempts: 0,
    createdAt: '2026-11-17T12:00:00+00:00',
    startedAt: null,
    finishedAt: null,
    campaignId: 'c-1',
    streamId: 's-2',
    retryOf: null,
    refusal: null,
    steps: [{ name: 'queued', at: '2026-11-17T12:00:00+00:00', note: '' }],
  }

  it('queues a task with the ID the browser made and answers with the task (R-ED-20, R-TK-04)', async () => {
    const { graphql, calls } = fakeBackend({ PublishStream: { result: task() } })

    const view = await publishStream(graphql, { streamId: 's-2', version: '3', body: { taskId: TASK_ID } })

    expect(calls).toEqual([{
      operation: 'PublishStream',
      variables: { input: { streamId: 's-2', taskId: TASK_ID, expectedVersion: 3 } },
    }])
    expect(view).toEqual(queued)
  })

  it('tells how a task is doing and why it was rejected (R-TK-05)', async () => {
    const rejected = task({
      status: 'REJECTED',
      attempts: 3,
      finishedAt: '2026-11-17T12:00:09+00:00',
      refusal: { message: 'Keitaro ответил 502', createdDomain: null },
    })
    const { graphql, calls } = fakeBackend({ TaskState: { task: rejected } })

    const view = await loadTask(graphql, TASK_ID)

    expect(calls).toEqual([{ operation: 'TaskState', variables: { id: TASK_ID } }])
    expect(view).toMatchObject({ status: 'rejected', finished: true, attempts: 3, refusal: 'Keitaro ответил 502' })
  })

  it('answers 404 for a task nobody queued', async () => {
    const { graphql } = fakeBackend({ TaskState: { task: null } })

    expect(await refusal(loadTask(graphql, TASK_ID))).toMatchObject({ status: 404, body: { code: 'task_not_found' } })
  })

  it('answers a conflict with the stream as it is now (R-CC-06)', async () => {
    const current = stream({ dirty: true, version: 4 })
    const { graphql } = fakeBackend({
      PublishStream: { result: { __typename: 'StreamConflict', message: 'Поток изменён', stream: current } },
    })

    const { status, body } = await refusal(publishStream(graphql, { streamId: 's-2', version: 3, body: { taskId: TASK_ID } }))

    expect(status).toBe(409)
    expect(body.stream).toMatchObject({ id: 's-2', version: 4 })
  })

  it.each([
    ['StreamBusy', 409, 'stream_busy'],
    ['StreamNotFound', 404, 'stream_not_found'],
    ['EmptyStream', 422, 'empty_stream'],
    ['TaskKeyReused', 409, 'task_key_reused'],
  ])('maps %s to %i', async (typename, status, code) => {
    const { graphql } = fakeBackend({ PublishStream: { result: { __typename: typename, message: 'почему' } } })

    expect(await refusal(publishStream(graphql, { streamId: 's-2', body: { taskId: TASK_ID } }))).toEqual({
      status,
      body: { code, message: 'почему' },
    })
  })

  it.each([
    [{ streamId: 's-2' }],
    [{ streamId: 's-2', body: { taskId: 'not-a-uuid' } }],
    [{ streamId: '', body: { taskId: TASK_ID } }],
  ])('rejects malformed %j without asking the backend', async (input) => {
    const { graphql, calls } = fakeBackend({})

    expect((await refusal(publishStream(graphql, input))).status).toBe(400)
    expect(calls).toHaveLength(0)
  })
})
