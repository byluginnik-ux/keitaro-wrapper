import { expect, test } from '@playwright/test'
import {
  A, B, C, D, addOffer, changeInTracker, expectDraft, expectRemoved, expectShares, failTracker, flow, inTracker,
  makeCampaign, offerRow, openCampaign, pinShare, publish,
} from './support'

test('S1: loading shows both streams as the tracker has them', async ({ page, request }) => {
  await openCampaign(page, await makeCampaign(request))

  await expect(flow(page, 'Flow 1')).toContainText('Поток без офферов')
  await expect(flow(page, 'Flow 1').getByRole('button')).toHaveCount(0)
  await expectShares(page, { 'Offer A': 34, 'Offer B': 33, 'Offer C': 33 })
  await expect(page.getByText('Не опубликовано')).toHaveCount(0)
})

test('S2: an added offer changes the draft and not the tracker', async ({ page, request }) => {
  const scenario = await makeCampaign(request)
  await openCampaign(page, scenario)

  await addOffer(page, 'offer d', 'Offer D')

  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })
  await expectDraft(page, true)
  await expect(offerRow(page, 'Offer D')).toContainText('Новый')
  await expect(offerRow(page, 'Offer A')).toContainText('Было 34')
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 34], [B, 33], [C, 33]])
})

test('S3: publishing sends the draft to the tracker', async ({ page, request }) => {
  const scenario = await makeCampaign(request)
  await openCampaign(page, scenario)
  await addOffer(page, 'offer d', 'Offer D')

  await publish(page)

  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 25], [B, 25], [C, 25], [D, 25]])
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })
  await expect(offerRow(page, 'Offer D')).not.toContainText('Новый')
})

test('S4: cancelling returns the stream to what is published', async ({ page, request }) => {
  await openCampaign(page, await makeCampaign(request))
  await addOffer(page, 'offer d', 'Offer D')
  await expectDraft(page, true)

  await page.getByRole('button', { name: 'Отменить' }).click()

  await expectShares(page, { 'Offer A': 34, 'Offer B': 33, 'Offer C': 33 })
  await expect(offerRow(page, 'Offer D')).toHaveCount(0)
  await expectDraft(page, false)
})

test('S5: a removed offer leaves the tracker and can be brought back', async ({ page, request }) => {
  const scenario = await makeCampaign(request, [[A, 25], [B, 25], [C, 25], [D, 25]])
  await openCampaign(page, scenario)

  await page.getByRole('button', { name: 'Удалить Offer B' }).click()
  await expectRemoved(page, 'Offer B')
  await expectShares(page, { 'Offer A': 34, 'Offer C': 33, 'Offer D': 33 })
  await expectDraft(page, true)

  await publish(page)
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 34], [C, 33], [D, 33]])
  await expectRemoved(page, 'Offer B')

  await page.getByRole('button', { name: 'Вернуть Offer B' }).click()
  await publish(page)
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 25], [B, 25], [C, 25], [D, 25]])
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })
})

test('S6: offers removed in the tracker become removed here', async ({ page, request }) => {
  const scenario = await makeCampaign(request, [[A, 25], [B, 25], [C, 25], [D, 25]])
  await openCampaign(page, scenario)

  await changeInTracker(request, scenario.offersStreamId, [[A, 60], [B, 40]])
  await page.getByRole('button', { name: 'Обновить из Keitaro' }).click()

  await expectShares(page, { 'Offer A': 60, 'Offer B': 40 })
  await expectRemoved(page, 'Offer C')
  await expectRemoved(page, 'Offer D')
  await expectDraft(page, false)
})

test('S7: a pinned share survives every recalculation', async ({ page, request }) => {
  const scenario = await makeCampaign(request, [[A, 25], [B, 25], [C, 25], [D, 25]])
  await openCampaign(page, scenario)
  await page.getByRole('button', { name: 'Удалить Offer D' }).click()
  await publish(page)
  await expectRemoved(page, 'Offer D')

  await pinShare(page, 'Offer C', 25)
  await expect(page.getByRole('button', { name: 'Доля закреплена: Offer C. Открепить' })).toBeVisible()
  await page.getByRole('button', { name: 'Вернуть Offer D' }).click()
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })

  await page.getByRole('button', { name: 'Удалить Offer D' }).click()
  await expectShares(page, { 'Offer A': 38, 'Offer B': 37, 'Offer C': 25 })
})

test('S8: pins that do not fit into 100 are refused and change nothing', async ({ page, request }) => {
  await openCampaign(page, await makeCampaign(request))
  await pinShare(page, 'Offer A', 60)
  await expectShares(page, { 'Offer A': 60, 'Offer B': 20, 'Offer C': 20 })

  await pinShare(page, 'Offer B', 50)

  await expect(flow(page, 'Flow 2').getByRole('alert')).toContainText('Действие не выполнено')
  await expectShares(page, { 'Offer A': 60, 'Offer B': 20, 'Offer C': 20 })
})

test('reloading is refused while a draft is not published (R-ED-06)', async ({ page, request }) => {
  await openCampaign(page, await makeCampaign(request))
  await addOffer(page, 'offer d', 'Offer D')
  await expectDraft(page, true)

  await page.getByRole('button', { name: 'Обновить из Keitaro' }).click()

  await expect(page.getByRole('alert')).toContainText('Кампания не обновлена')
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })
})

test('a failure of the tracker keeps the draft (R-ED-22, R-UX-16)', async ({ page, request }) => {
  const scenario = await makeCampaign(request)
  await openCampaign(page, scenario)
  await addOffer(page, 'offer d', 'Offer D')

  await failTracker(request, 'replace_stream_offers', true)
  try {
    await page.getByRole('button', { name: 'Опубликовать' }).click()
    await expect(flow(page, 'Flow 2').getByRole('alert')).toContainText('Действие не выполнено')
  }
  finally {
    await failTracker(request, 'replace_stream_offers', false)
  }
  await expectDraft(page, true)
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })

  await publish(page)
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 25], [B, 25], [C, 25], [D, 25]])
})

test('the draft is still there after the page is reloaded', async ({ page, request }) => {
  await openCampaign(page, await makeCampaign(request))
  await addOffer(page, 'offer d', 'Offer D')
  await expectDraft(page, true)

  await page.reload()

  await expectDraft(page, true)
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })
})

test('an offer is added, pinned and published without a mouse (R-UX-15)', async ({ page, request }) => {
  const scenario = await makeCampaign(request)
  await openCampaign(page, scenario)

  await page.getByRole('combobox', { name: 'Добавить оффер в Flow 2' }).focus()
  await page.keyboard.type('offer d')
  await expect(page.getByRole('option')).toHaveText(['Offer D11114'])
  await page.keyboard.press('Enter')
  await expectShares(page, { 'Offer A': 25, 'Offer B': 25, 'Offer C': 25, 'Offer D': 25 })

  await page.getByRole('button', { name: /^Доля оффера Offer A: / }).focus()
  await page.keyboard.press('Enter')
  await page.keyboard.type('40')
  await page.keyboard.press('Enter')
  await expectShares(page, { 'Offer A': 40, 'Offer B': 20, 'Offer C': 20, 'Offer D': 20 })
  await expect(page.getByRole('button', { name: /^Доля оффера Offer A: / })).toBeFocused()

  await page.getByRole('button', { name: 'Опубликовать' }).focus()
  await page.keyboard.press('Enter')
  await expectDraft(page, false)
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 40], [B, 20], [C, 20], [D, 20]])
})

test('the browser talks only to its own server (R-ARCH-04)', async ({ page, request }) => {
  const foreign: string[] = []
  page.on('request', (sent) => {
    if (!sent.url().startsWith('http://127.0.0.1:3919/')) foreign.push(sent.url())
  })

  await openCampaign(page, await makeCampaign(request))
  await addOffer(page, 'offer d', 'Offer D')
  await publish(page)

  expect(foreign).toEqual([])
})

test('a stream changed in another window is shown as it is now (R-CC-06, R-UX-17)', async ({ page, context, request }) => {
  await openCampaign(page, await makeCampaign(request))
  const other = await context.newPage()
  await other.goto(page.url())
  await other.getByRole('button', { name: 'Удалить Offer B' }).click()
  await expectRemoved(other, 'Offer B')

  await addOffer(page, 'offer d', 'Offer D')

  await expect(flow(page, 'Flow 2').getByRole('alert')).toContainText('Поток изменён')
  await expectRemoved(page, 'Offer B')
  await expectShares(page, { 'Offer A': 50, 'Offer C': 50 })
  await expect(offerRow(page, 'Offer D')).toHaveCount(0)

  await addOffer(page, 'offer d', 'Offer D')

  await expectShares(page, { 'Offer A': 34, 'Offer C': 33, 'Offer D': 33 })
  await expect(flow(page, 'Flow 2').getByRole('alert')).toHaveCount(0)
})
