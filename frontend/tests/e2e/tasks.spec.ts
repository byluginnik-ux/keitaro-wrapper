import { expect, test } from '@playwright/test'
import { A, B, C, D, addOffer, expectDraft, failTracker, flow, inTracker, makeCampaign, openCampaign } from './support'

test('a rejected publication is found among the tasks and repeated (R-UX-30, R-UX-31, R-TK-09)', async ({ page, request }) => {
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
  const campaign = page.url()

  await page.getByRole('link', { name: 'Задачи' }).click()
  await expect(page.getByRole('heading', { name: 'Очередь' })).toBeVisible()
  await page.getByLabel('Статус').selectOption('rejected')
  const rejected = page.locator('[data-task]').first()
  await expect(rejected).toContainText('Отклонена')
  await expect(rejected).toContainText('Причина:')
  await rejected.getByRole('button', { name: /Повторить/ }).click()

  await page.getByLabel('Статус').selectOption('succeeded')
  await expect(page.locator('[data-task]').first()).toContainText('повтор')
  expect(await inTracker(request, scenario.offersStreamId)).toEqual([[A, 25], [B, 25], [C, 25], [D, 25]])
  await page.goto(campaign)
  await expectDraft(page, false)
})

test('the tasks page tells who listens to the queue (R-UX-30)', async ({ page }) => {
  await page.goto('/tasks')

  await expect(page.getByText('keitaro.tasks:').first()).toContainText('обработчиков 1')
  await expect(page.getByText('Обработчиков нет')).toHaveCount(0)
})
