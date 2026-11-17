// Records the demo and checks the assignment: drives the real interface against the tracker and,
// after every change, compares what Keitaro itself holds (read through its Admin API) with what
// the assignment asks for. A mismatch ends the run with an error; the campaign is removed anyway.
// Run from the repository root: node demo/record.mjs  (the service on DEMO_URL, .env with the key)
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const require = createRequire(new URL('../frontend/package.json', import.meta.url))
const { chromium } = require('@playwright/test')

const URL_ = process.env.DEMO_URL ?? 'http://127.0.0.1:3929'
const OUT = process.env.DEMO_OUT ?? 'demo/out'
const ENV_FILE = process.env.DEMO_ENV ?? '.env'
const env = Object.fromEntries(
  readFileSync(ENV_FILE, 'utf8').split('\n').filter(line => line.includes('=') && !line.startsWith('#'))
    .map(line => [line.slice(0, line.indexOf('=')), line.slice(line.indexOf('=') + 1).trim()]),
)
const API = `${env.KEITARO_BASE_URL.replace(/\/$/, '')}/admin_api/v1`
const NAME = `demo_${new Date().toISOString().slice(5, 16).replace(/[-T:]/g, '')}`
const [first, second, third] = (process.env.DEMO_OFFERS ?? '24800,25327,19958').split(',')
const OFFERS = { first, second, third }
const COUNTRY = { typed: 'каз', option: /Казахстан/, code: 'KZ' }
// the fake tracker of the tests answers without filters and redirects: those checks need the real one
const LIVE = !/127\.0\.0\.1|localhost/.test(API)

async function write(method, path, body) {
  const headers = { 'Api-Key': env.KEITARO_API_KEY, 'Accept': 'application/json', 'Content-Type': 'application/json' }
  const response = await fetch(API + path, { method, headers, body: JSON.stringify(body) })
  if (!response.ok) throw new Error(`Keitaro ${response.status} on ${method} ${path}`)
  return response.json()
}

async function tracker(method, path) {
  const response = await fetch(API + path, { method, headers: { 'Api-Key': env.KEITARO_API_KEY, 'Accept': 'application/json' } })
  if (!response.ok) throw new Error(`Keitaro ${response.status} on ${method} ${path}`)
  return response.json()
}

const pause = ms => new Promise(resolve => setTimeout(resolve, ms))
const escaped = text => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

/** What the run has proved, by item of the assignment. */
const results = []

function check(item, step, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  results.push({ item, step, ok })
  if (!ok) throw new Error(`${item} — ${step}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
}

/** The tracker keeps its own order of offers: compositions are compared as sets. */
const pairs = (...list) => list.sort((left, right) => left[0] - right[0])

/** The offers the tracker holds in the stream with offers, as [id, share]. */
function held(streams) {
  const stream = streams.find(item => item.schema === 'landings')
  return pairs(...(stream?.offers ?? []).filter(offer => offer.state !== 'deleted').map(offer => [offer.offer_id, offer.share]))
}
const marks = []
const started = Date.now()

/** The caption at the bottom of the frame; survives navigation because it is re-added. */
async function say(page, title, text = '') {
  marks.push({ at: (Date.now() - started) / 1000, title })
  await page.evaluate(([title, text]) => {
    let bar = document.getElementById('demo-caption')
    if (!bar) {
      bar = document.createElement('div')
      bar.id = 'demo-caption'
      bar.style.cssText = 'position:fixed;left:50%;bottom:20px;transform:translateX(-50%);z-index:99999;max-width:1000px;'
        + 'padding:11px 19px;border-radius:10px;background:rgba(17,20,28,.95);border:1px solid rgba(255,255,255,.28);color:#fff;font:500 18px/1.35 system-ui,sans-serif;'
        + 'box-shadow:0 12px 40px rgba(0,0,0,.35);text-align:center;pointer-events:none'
      document.body.append(bar)
    }
    bar.innerHTML = `<b style="font-weight:700">${title}</b>${text ? `<span style="opacity:.82"> — ${text}</span>` : ''}`
  }, [title, text])
}

/** A card with what the tracker holds right now. */
async function showTracker(page, campaignId, note) {
  const [campaign, streams] = await Promise.all([
    tracker('GET', `/campaigns/${campaignId}`),
    tracker('GET', `/campaigns/${campaignId}/streams`),
  ])
  const rows = streams.map((stream) => {
    const filters = (stream.filters ?? []).map(filter => `${filter.name}: ${[].concat(filter.payload).join(', ')}`).join('; ')
    const offers = (stream.offers ?? []).map(offer => `${offer.offer_id} — ${offer.share} %`).join('<br>')
    const body = stream.schema === 'redirect'
      ? `фильтр ${filters || '—'} → ${stream.action_payload}`
      : offers || 'офферов нет'
    return `<tr><td style="padding:6px 12px 6px 0;vertical-align:top;white-space:nowrap;opacity:.7">${stream.name}</td><td style="padding:6px 0">${body}</td></tr>`
  }).join('')
  await page.evaluate(([name, id, rows, note]) => {
    document.getElementById('demo-tracker')?.remove()
    const card = document.createElement('div')
    card.id = 'demo-tracker'
    card.style.cssText = 'position:fixed;right:28px;top:76px;z-index:99998;width:380px;padding:18px 20px;border-radius:12px;border:1px solid rgba(255,255,255,.22);'
      + 'background:#0f1b2d;color:#fff;font:400 15px/1.4 system-ui,sans-serif;box-shadow:0 18px 60px rgba(0,0,0,.4);pointer-events:none'
    card.innerHTML = `<div style="font:700 11px/1 system-ui;letter-spacing:.12em;text-transform:uppercase;color:#7fd1ae">Keitaro Admin API · ${note}</div>`
      + `<div style="margin:8px 0 4px;font-weight:700;font-size:17px">${name}</div><div style="opacity:.6;font-size:12px">кампания ${id}</div>`
      + `<table style="margin-top:8px;border-collapse:collapse;font-size:15px">${rows}</table>`
    document.body.append(card)
  }, [campaign.name, campaign.id, rows, note])
  await pause(6090)
  await page.evaluate(() => document.getElementById('demo-tracker')?.remove())
  return { campaign, streams }
}

/** The shares the page shows, by offer ID; a removed offer shows 0. */
async function shown(page) {
  const shares = {}
  for (const id of Object.values(OFFERS)) {
    const item = row(page, id)
    if (await item.count() === 0) continue
    // the name of an offer may itself hold a percentage
    shares[id] = Number((await item.innerText()).replaceAll(names[id], '').match(/(\d+)\s*%/)?.[1])
  }
  return shares
}

async function pin(page, offer, share) {
  await page.getByRole('button', { name: new RegExp(`^Доля оффера ${escaped(names[offer])}: `) }).click()
  const input = page.getByRole('textbox', { name: new RegExp(`^Доля оффера ${escaped(names[offer])}`) })
  await input.pressSequentially(String(share), { delay: 160 })
  await pause(725)
  await input.press('Enter')
}

async function add(page, id) {
  const box = page.getByRole('combobox', { name: 'Добавить оффер в Flow 2' })
  await box.click()
  await box.fill('')
  await box.pressSequentially(id, { delay: 110 })
  await page.getByRole('option').first().click()
}

const publish = page => page.getByRole('button', { name: 'Опубликовать' }).click()
const row = (page, id) => page.getByRole('region', { name: 'Flow 2' }).getByRole('listitem').filter({ hasText: names[id] })
/** The publication is a task: it has ended when the stream is neither being published nor a draft. */
async function published(page) {
  await pause(300)
  await page.getByText('Публикуется…').waitFor({ state: 'detached', timeout: 60_000 })
  await page.getByText('Не опубликовано').waitFor({ state: 'detached', timeout: 60_000 })
}
const ids = (...keys) => keys.map(key => Number(OFFERS[key]))

// offers are named on the page; the run speaks of them by ID
const names = Object.fromEntries(
  (await tracker('GET', '/offers')).filter(offer => Object.values(OFFERS).includes(String(offer.id)))
    .map(offer => [String(offer.id), offer.name]),
)
for (const id of Object.values(OFFERS)) if (!names[id]) throw new Error(`the tracker has no offer ${id}`)
const group = (await tracker('GET', '/groups?type=campaigns')).find(item => item.name === 'FORTESTS')
const source = (await tracker('GET', '/traffic_sources')).find(item => item.name === 'FORTESTS')
const domains = await tracker('GET', '/domains')

const browser = await chromium.launch({ executablePath: process.env.E2E_CHROMIUM ?? '/usr/bin/chromium' })
const context = await browser.newContext({
  viewport: { width: 1920, height: 1080 },
  recordVideo: { dir: OUT, size: { width: 1920, height: 1080 } },
  colorScheme: 'light',
})
await context.addInitScript(() => {
  const ZOOM = 1.5
  const setup = () => {
    if (!location.protocol.startsWith('http')) return
    document.documentElement.style.zoom = String(ZOOM)
    const dot = document.createElement('div')
    dot.id = 'demo-cursor'
    dot.style.cssText = 'position:fixed;z-index:100000;width:16px;height:16px;margin:-8px 0 0 -8px;border-radius:50%;'
      + 'background:rgba(20,150,95,.55);border:1.5px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.35);pointer-events:none;left:-40px;top:-40px;'
      + 'transition:left .18s ease-out,top .18s ease-out'
    document.documentElement.append(dot)
    addEventListener('mousemove', (event) => {
      dot.style.left = `${event.clientX / ZOOM}px`
      dot.style.top = `${event.clientY / ZOOM}px`
    }, true)
  }
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', setup)
  else setup()
})
const page = await context.newPage()

/** A full-frame card: the title and the closing frame. */
async function card(title, lines, ms) {
  await page.setContent(`<body style="margin:0;height:100vh;display:grid;place-content:center;gap:28px;background:#0f1b2d;color:#fff;font-family:system-ui,sans-serif;text-align:center">
    <div style="font:700 20px/1 system-ui;letter-spacing:.18em;text-transform:uppercase;color:#7fd1ae">Тестовое задание · Keitaro Wrapper</div>
    <div style="font:700 76px/1.1 system-ui">${title}</div>
    <div style="font:400 32px/1.5 system-ui;opacity:.82">${lines.join('<br>')}</div></body>`)
  await pause(ms)
}
let campaignId = null
try {
  await card('Создаватор кампаний<br>и редактор офферов', ['Запись на живом Keitaro: кампания создаётся и правится в трекере.', 'Справа — что возвращает Admin API после каждого шага.'], 5500)
  // 1. the creator
  await page.goto(`${URL_}/create`)
  await say(page, 'Часть 1. Создаватор', 'название, страна, оффер, домен, группа, источник')
  await pause(3625)
  await page.getByRole('button', { name: 'Создать кампанию' }).click()
  await say(page, 'Пустая форма не уходит', 'у каждого поля своя подсказка')
  await pause(4350)
  await page.getByLabel('Название').pressSequentially(NAME, { delay: 70 })
  await page.getByRole('combobox', { name: 'Страна' }).pressSequentially(COUNTRY.typed, { delay: 120 })
  await page.getByRole('option', { name: COUNTRY.option }).click()
  await say(page, 'Оффер ищется в Keitaro', 'по названию или ID')
  await page.getByRole('combobox', { name: 'Оффер' }).pressSequentially(OFFERS.first, { delay: 120 })
  await page.getByRole('option').first().click()
  await page.getByRole('combobox', { name: 'Домен' }).click()
  const domainName = (await page.getByRole('option').first().innerText()).trim()
  const domain = domains.find(item => domainName.includes(item.name))
  await page.getByRole('option').first().click()
  // a list of one is chosen by the form itself: clear the field before typing
  for (const field of ['Группа', 'Источник трафика']) {
    const box = page.getByRole('combobox', { name: field })
    await box.fill('')
    await box.pressSequentially('FORT', { delay: 120 })
    await page.getByRole('option', { name: /FORTESTS/ }).click()
  }
  await say(page, 'Домен, группа и источник', 'справочники из Admin API')
  await pause(3190)
  await page.getByRole('button', { name: 'Создать кампанию' }).click()
  const creating = await page.getByRole('status').filter({ hasText: 'Создаётся' }).waitFor({ timeout: 3000 }).then(() => true, () => false)
  if (creating) await say(page, 'Создание — задача', 'запрос поставил её и ответил, в Keitaro пишет обработчик')
  await page.getByText('Кампания создана').waitFor({ timeout: 60_000 })
  const link = await page.getByRole('link', { name: 'Открыть в Keitaro' }).getAttribute('href')
  campaignId = Number(link.split('/').pop())
  await say(page, 'Кампания создана в Keitaro', `ID ${campaignId}`)
  await pause(2610)
  const made = await showTracker(page, campaignId, 'после создания')
  check('Создаватор: название, страна, ID оффера', 'кампания есть в трекере под своим именем', made.campaign.name, `${env.CAMPAIGN_NAME_PREFIX ?? 'test_bulygin_'}${NAME}`)
  check('Создаватор: домен, группа, источник', 'выбранные в форме', [made.campaign.domain_id, made.campaign.group_id, made.campaign.traffic_source_id], [domain?.id, group?.id, source?.id])
  check('Создаватор: два потока', 'по позициям', made.streams.map(stream => [stream.position, stream.schema]).sort(), [[1, 'redirect'], [2, 'landings']])
  if (LIVE) {
    const redirect = made.streams.find(stream => stream.schema === 'redirect')
    check('Создаватор: поток 1 ловит страну и ведёт на Google', 'фильтр и адрес',
      [(redirect.filters ?? []).map(filter => [filter.name, filter.mode, [].concat(filter.payload)]), redirect.action_payload],
      [[['country', 'accept', [COUNTRY.code]]], 'https://google.com'])
  }
  check('Создаватор: поток 2 ведёт на выбранный оффер', 'один оффер, доля 100', held(made.streams), pairs([Number(OFFERS.first), 100]))
  await say(page, 'Два потока', 'страна → google.com, остальные → оффер 100 %')
  await pause(3625)

  // 2. the editor
  await page.getByRole('link', { name: 'В редактор' }).click()
  await page.getByRole('region', { name: 'Flow 2' }).waitFor()
  await say(page, 'Часть 2. Редактор', 'поток 1 — редирект, поток 2 — оффер 100 %')
  await pause(4640)
  await add(page, OFFERS.second)
  await row(page, OFFERS.second).waitFor()
  await say(page, 'Добавили оффер', 'доли 50 / 50, поток помечен «Не опубликовано»')
  await pause(3770)
  await add(page, OFFERS.third)
  await row(page, OFFERS.third).waitFor()
  await say(page, 'Ещё один', '34 / 33 / 33 — сумма всегда 100')
  await pause(3770)
  check('Редактор: цифры', 'три оффера делят 100', await shown(page), { [OFFERS.first]: 34, [OFFERS.second]: 33, [OFFERS.third]: 33 })
  const draft = await showTracker(page, campaignId, 'черновик не отправлен')
  check('Редактор: добавление', 'черновик не меняет трекер', held(draft.streams), pairs([Number(OFFERS.first), 100]))
  await say(page, 'В Keitaro пока прежний состав', 'изменения копятся в черновике')
  await pause(3190)
  await publish(page)
  await published(page)
  await say(page, '«Опубликовать»', 'публикация — задача; состав и доли ушли в Keitaro')
  await pause(2175)
  const three = await showTracker(page, campaignId, 'после публикации')
  const [a, b, c] = ids('first', 'second', 'third')
  check('Редактор: добавление', 'после публикации в трекере три оффера', held(three.streams), pairs([a, 34], [b, 33], [c, 33]))

  await page.getByRole('button', { name: new RegExp(`^Удалить ${escaped(names[OFFERS.second])}`) }).click()
  await say(page, 'Удалили оффер', 'он остаётся в потоке: «Удалён», 0 %, доли пересчитаны')
  await pause(4350)
  check('Редактор: цифры', 'удалённый — 0, остальные 50 / 50', await shown(page), { [OFFERS.first]: 50, [OFFERS.second]: 0, [OFFERS.third]: 50 })
  await publish(page)
  await published(page)
  const two = await showTracker(page, campaignId, 'оффер удалён')
  check('Редактор: удаление', 'после публикации оффера нет в трекере', held(two.streams), pairs([a, 50], [c, 50]))
  await page.getByRole('button', { name: new RegExp(`^Вернуть ${escaped(names[OFFERS.second])}`) }).click()
  await say(page, '«Вернуть»', 'оффер снова активен, доли снова 34 / 33 / 33')
  await pause(3770)
  await publish(page)
  await published(page)
  const back = await showTracker(page, campaignId, 'оффер возвращён')
  check('Редактор: возврат удалённого', 'оффер снова в трекере', held(back.streams), pairs([a, 34], [b, 33], [c, 33]))

  await say(page, 'Закрепление доли', 'нажать на долю, ввести число, Enter')
  await pin(page, OFFERS.first, 60)
  await pause(1160)
  await say(page, 'Доля 60 % закреплена', 'остальные делят остаток: 20 / 20')
  await pause(4350)
  check('Редактор: закрепление доли', 'остальные делят остаток', await shown(page), { [OFFERS.first]: 60, [OFFERS.second]: 20, [OFFERS.third]: 20 })
  await page.getByRole('button', { name: new RegExp(`^Удалить ${escaped(names[OFFERS.third])}`) }).click()
  await say(page, 'Удалили оффер при закреплённой доле', '60 % на месте, остаток у оставшегося')
  await pause(3770)
  check('Редактор: закрепление доли', 'закреплённая не меняется при пересчёте', await shown(page), { [OFFERS.first]: 60, [OFFERS.second]: 40, [OFFERS.third]: 0 })
  await pin(page, OFFERS.second, 50)
  await page.getByRole('region', { name: 'Flow 2' }).getByRole('alert').waitFor()
  await say(page, 'Отказ: 60 + 50 больше 100', 'доли не изменились')
  await pause(5075)
  check('Редактор: переполнение', 'отказ, доли прежние', await shown(page), { [OFFERS.first]: 60, [OFFERS.second]: 40, [OFFERS.third]: 0 })
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: 'Отменить' }).click()
  await page.getByText('Не опубликовано').waitFor({ state: 'detached' })
  await say(page, '«Отменить»', 'поток вернулся к опубликованному состоянию')
  await pause(4060)
  check('Редактор: отмена', 'на странице опубликованный состав', await shown(page), { [OFFERS.first]: 34, [OFFERS.second]: 33, [OFFERS.third]: 33 })
  check('Редактор: отмена', 'в трекер ничего не ушло', held(await tracker('GET', `/campaigns/${campaignId}/streams`)), pairs([a, 34], [b, 33], [c, 33]))

  // the composition is changed in the tracker itself, behind the back of the service
  const stream = back.streams.find(item => item.schema === 'landings')
  await write('PUT', `/streams/${stream.id}`, { offers: [{ offer_id: a, share: 50 }, { offer_id: b, share: 50 }] })
  await say(page, 'Состав изменили в самом Keitaro', 'третий оффер убран через Admin API')
  await showTracker(page, campaignId, 'изменено в Keitaro')
  await page.getByRole('button', { name: 'Обновить из Keitaro' }).click()
  await page.getByRole('button', { name: new RegExp(`^Вернуть ${escaped(names[OFFERS.third])}`) }).waitFor({ timeout: 60_000 })
  await say(page, '«Обновить из Keitaro»', 'убранный оффер помечен «Удалён», доли как в трекере')
  await pause(4350)
  check('Редактор: изменение в самом Keitaro', 'после обновления убранный оффер — 0, остальные как в трекере', await shown(page), { [OFFERS.first]: 50, [OFFERS.second]: 50, [OFFERS.third]: 0 })

  await page.getByRole('link', { name: 'Задачи' }).click()
  await page.locator('[data-task]').first().waitFor()
  await say(page, 'Задачи', 'каждое создание и публикация — задача с итогом; отклонённую можно повторить')
  await pause(4350)

  const theme = page.getByRole('button', { name: /Тема:/ })
  await theme.click()
  await theme.click()
  await say(page, 'Светлая и тёмная темы', 'управление с клавиатуры, состояние не только цветом')
  await pause(4350)
  await page.goto(`${URL_}/`)
  await say(page, 'Список кампаний сервиса', 'любую кампанию трекера можно открыть по её ID')
  await pause(4350)
  await card('Что внутри', ['FastAPI + GraphQL · Nuxt и BFF на Nitro · Postgres или MongoDB', 'Задачи, outbox, RabbitMQ, Redis · 368 тестов бэкенда, 170 интерфейса, 21 сквозной сценарий', 'github.com/byluginnik-ux/keitaro-wrapper'], 6500)
}
finally {
  await context.close()
  await browser.close()
  if (campaignId) {
    const removed = await tracker('DELETE', `/campaigns/${campaignId}`)
    console.log('deleted in the tracker:', campaignId, [].concat(removed)[0]?.state)
  }
  for (const { item, step, ok } of results) console.log(`${ok ? 'OK  ' : 'FAIL'} ${item} — ${step}`)
  console.log(`checks: ${results.filter(result => result.ok).length} of ${results.length} passed${LIVE ? '' : ' (fake tracker: the filter and the redirect of stream 1 are not checked)'}`)
  console.log(JSON.stringify({ seconds: (Date.now() - started) / 1000, marks }))
  console.log('video:', await page.video()?.path())
}
