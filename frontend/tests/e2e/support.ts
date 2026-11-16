import type { APIRequestContext, Page } from '@playwright/test'
import { expect } from '@playwright/test'

export const TRACKER = 'http://127.0.0.1:8791'
export const A = 11111
export const B = 11112
export const C = 11113
export const D = 11114

export interface Scenario {
  campaignId: number
  redirectStreamId: number
  offersStreamId: number
}

type Composition = [offerId: number, share: number][]

/** The starting point of the scenarios of SPEC.md: a redirect stream and a stream with offers. */
export async function makeCampaign(
  request: APIRequestContext,
  offers: Composition = [[A, 34], [B, 33], [C, 33]],
): Promise<Scenario> {
  const response = await request.post(`${TRACKER}/__test/campaign`, { data: { offers } })
  expect(response.ok()).toBe(true)
  return await response.json() as Scenario
}

/** What the tracker holds in a stream right now. */
export async function inTracker(request: APIRequestContext, streamId: number): Promise<Composition> {
  return await (await request.get(`${TRACKER}/__test/streams/${streamId}/offers`)).json() as Composition
}

/** Change a stream the way an operator would in the tracker's own admin panel. */
export async function changeInTracker(request: APIRequestContext, streamId: number, offers: Composition) {
  expect((await request.put(`${TRACKER}/__test/streams/${streamId}/offers`, { data: { offers } })).ok()).toBe(true)
}

export async function failTracker(request: APIRequestContext, method: string, on: boolean) {
  expect((await request.post(`${TRACKER}/__test/fail`, { data: { method, on } })).ok()).toBe(true)
}

/** S1: open the campaign by its tracker id, which loads its streams. */
export async function openCampaign(page: Page, scenario: Scenario) {
  await page.goto('/')
  await page.getByLabel('Открыть кампанию из Keitaro').fill(String(scenario.campaignId))
  await page.getByRole('button', { name: 'Открыть' }).click()
  await expect(page.getByRole('heading', { level: 1, name: `test_bulygin_scenario_${scenario.campaignId}` })).toBeVisible()
}

export function flow(page: Page, name: string) {
  return page.getByRole('region', { name })
}

export function offerRow(page: Page, offer: string) {
  return flow(page, 'Flow 2').getByRole('listitem').filter({ hasText: offer })
}

/** Shares of active offers in the order of the stream, read from what the user sees. */
export async function expectShares(page: Page, expected: Record<string, number>) {
  await expect.poll(async () => {
    const labels = await flow(page, 'Flow 2').getByRole('button', { name: /^Доля оффера / }).evaluateAll(
      buttons => buttons.map(button => button.getAttribute('aria-label') ?? ''),
    )
    return Object.fromEntries(labels.map((label) => {
      const [, offer, share] = /^Доля оффера (.+): (\d+) %/.exec(label) ?? []
      return [offer, Number(share)]
    }))
  }).toEqual(expected)
}

export async function expectRemoved(page: Page, offer: string) {
  const row = offerRow(page, offer)
  await expect(row).toContainText('Удалён')
  await expect(row).toContainText('0 %')
  await expect(row.getByRole('button', { name: `Вернуть ${offer}` })).toBeVisible()
}

export async function expectDraft(page: Page, dirty: boolean) {
  await expect(flow(page, 'Flow 2').getByText('Не опубликовано')).toHaveCount(dirty ? 1 : 0)
  await expect(page.getByRole('button', { name: 'Опубликовать' })).toHaveCount(dirty ? 1 : 0)
}

export async function addOffer(page: Page, search: string, offer: string) {
  const box = page.getByRole('combobox', { name: 'Добавить оффер в Flow 2' })
  await box.fill(search)
  await page.getByRole('option', { name: offer }).click()
}

export async function publish(page: Page) {
  await page.getByRole('button', { name: 'Опубликовать' }).click()
  await expectDraft(page, false)
}

export async function pinShare(page: Page, offer: string, share: number) {
  await page.getByRole('button', { name: new RegExp(`^Доля оффера ${offer}: `) }).click()
  const input = page.getByRole('textbox', { name: `Доля оффера ${offer}, %` })
  await input.fill(String(share))
  await input.press('Enter')
}
