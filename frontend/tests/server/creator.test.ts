import { describe, expect, it } from 'vitest'
import { createCampaign, loadCreatorOptions, searchOffers } from '../../server/utils/creator'
import { CAMPAIGN, fakeBackend, refusal } from './support'

const INPUT = {
  name: 'test_bulygin_au',
  country: 'AU',
  offerId: 11111,
  groupId: 10332,
  trafficSourceId: 836,
  domainId: 1813,
}
const INFO = { campaignNamePrefix: 'test_bulygin_', trackerUrl: 'https://tracker.test' }

describe('creator options', () => {
  it('gathers the whole form in one backend query (R-UX-02)', async () => {
    const { graphql, calls } = fakeBackend({
      CreatorOptions: {
        serviceInfo: INFO,
        domains: [{ id: 1813, name: 'tracker.example.com' }],
        groups: [{ id: 10332, name: 'FORTESTS' }],
        trafficSources: [{ id: 836, name: 'FORTESTS' }],
        countries: [{ code: 'AU', name: 'Австралия' }],
      },
    })

    const options = await loadCreatorOptions(graphql)

    expect(calls).toHaveLength(1)
    expect(options).toEqual({
      namePrefix: 'test_bulygin_',
      domains: [{ id: 1813, name: 'tracker.example.com' }],
      groups: [{ id: 10332, name: 'FORTESTS' }],
      trafficSources: [{ id: 836, name: 'FORTESTS' }],
      countries: [{ id: 'AU', name: 'Австралия' }],
    })
  })
})

describe('offer search', () => {
  it('asks the backend for a short list', async () => {
    const { graphql, calls } = fakeBackend({ SearchOffers: { offers: [{ id: 11111, name: 'Offer A' }] } })

    const offers = await searchOffers(graphql, { search: ' flex ' })

    expect(offers).toEqual([{ id: 11111, name: 'Offer A' }])
    expect(calls[0]?.variables).toEqual({ search: 'flex', limit: 20 })
  })

  it('searches for everything when nothing is typed', async () => {
    const { graphql, calls } = fakeBackend({ SearchOffers: { offers: [] } })

    await searchOffers(graphql, {})

    expect(calls[0]?.variables).toEqual({ search: '', limit: 20 })
  })
})

describe('create campaign', () => {
  it('returns the campaign with a link into the tracker (R-UX-04)', async () => {
    const { graphql, calls } = fakeBackend({
      CreateCampaign: { createCampaign: { __typename: 'Campaign', ...CAMPAIGN } },
      TrackerUrl: { serviceInfo: INFO },
    })

    const campaign = await createCampaign(graphql, INPUT)

    expect(campaign).toEqual({
      ...CAMPAIGN,
      trackerLink: 'https://tracker.test/admin/#!/campaigns/93212',
    })
    expect(calls[0]).toEqual({ operation: 'CreateCampaign', variables: { input: INPUT } })
  })

  it('sends a new domain name instead of an existing domain (R-CR-10)', async () => {
    const { graphql, calls } = fakeBackend({
      CreateCampaign: { createCampaign: { __typename: 'Campaign', ...CAMPAIGN } },
      TrackerUrl: { serviceInfo: INFO },
    })
    const { domainId: _omitted, ...rest } = INPUT

    await createCampaign(graphql, { ...rest, newDomainName: 'new.example.com' })

    expect(calls[0]?.variables).toEqual({ input: { ...rest, newDomainName: 'new.example.com' } })
  })

  it('rejects malformed input before the backend is asked', async () => {
    const { graphql, calls } = fakeBackend({})

    const { status, body } = await refusal(createCampaign(graphql, { ...INPUT, offerId: 'x', name: '' }))

    expect(status).toBe(400)
    expect(body.code).toBe('invalid_input')
    expect(body.fields?.map(item => item.field).sort()).toEqual(['name', 'offerId'])
    expect(calls).toHaveLength(0)
  })

  it('passes the backend\'s remarks on, field by field (R-UX-03)', async () => {
    const fields = [{ field: 'name', message: 'Название начинается с «test_bulygin_»' }]
    const { graphql } = fakeBackend({
      CreateCampaign: { createCampaign: { __typename: 'ValidationFailed', message: 'Проверьте поля: name', fields } },
    })

    const { status, body } = await refusal(createCampaign(graphql, INPUT))

    expect(status).toBe(422)
    expect(body).toEqual({ code: 'validation_failed', message: 'Проверьте поля: name', fields })
  })

  it('reports a tracker failure and the domain left behind (R-CR-12)', async () => {
    const { graphql } = fakeBackend({
      CreateCampaign: {
        createCampaign: {
          __typename: 'KeitaroFailure',
          message: 'Keitaro не создал кампанию. Домен new.example.com создан и остался в трекере.',
          createdDomain: { id: 7, name: 'new.example.com' },
        },
      },
    })

    const { status, body } = await refusal(createCampaign(graphql, INPUT))

    expect(status).toBe(502)
    expect(body.code).toBe('keitaro_failure')
    expect(body.message).toContain('new.example.com')
  })
})
