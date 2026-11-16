import { expect, test } from '@playwright/test'
import { TRACKER, expectShares, flow } from './support'

interface TrackerCampaign { id: number, name: string }

test('a campaign is created with a new domain and opened in the editor (R-UX-01…05)', async ({ page, request }) => {
  const name = `e2e_${Date.now()}`
  const host = `e2e-${Date.now()}.example.com`
  await page.goto('/create')

  await page.getByLabel('Название').fill(name)
  await page.getByRole('combobox', { name: 'Страна' }).fill('авст')
  await page.getByRole('option', { name: /Австралия/ }).click()
  await page.getByRole('combobox', { name: 'Оффер' }).fill('offer b')
  await page.getByRole('option', { name: /Offer B/ }).click()
  await page.getByRole('combobox', { name: 'Домен' }).fill(host)
  await page.getByRole('option', { name: `Создать домен ${host}` }).click()
  await expect(page.getByText('Новый домен: будет создан в Keitaro при отправке формы')).toBeVisible()
  await page.getByRole('button', { name: 'Создать кампанию' }).click()

  await expect(page.getByText('Кампания создана')).toBeVisible()
  await expect(page.getByText(`test_bulygin_${name}`)).toBeVisible()
  const campaigns = await (await request.get(`${TRACKER}/__test/campaigns`)).json() as TrackerCampaign[]
  expect(campaigns.map(campaign => campaign.name)).toContain(`test_bulygin_${name}`)

  await page.getByRole('link', { name: 'В редактор' }).click()
  await expect(flow(page, 'Flow 1')).toContainText('Поток без офферов')
  await expectShares(page, { 'Offer B': 100 })
})

test('an empty form names every field and sends nothing (R-UX-03)', async ({ page }) => {
  const sent: string[] = []
  page.on('request', item => item.method() === 'POST' && sent.push(item.url()))
  await page.goto('/create')

  await page.getByRole('button', { name: 'Создать кампанию' }).click()

  await expect(page.getByText('Введите продолжение названия')).toBeVisible()
  await expect(page.getByText('Выберите страну')).toBeVisible()
  await expect(page.getByText('Выберите оффер')).toBeVisible()
  expect(sent).toEqual([])
})
