// @vitest-environment happy-dom
import type { VueWrapper } from '@vue/test-utils'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import CreatorForm from '../../app/components/creator/CreatorForm.vue'
import CreatorResult from '../../app/components/creator/CreatorResult.vue'
import type { CreatorOptions } from '../../shared/types/api'

const OPTIONS: CreatorOptions = {
  namePrefix: 'test_bulygin_',
  domains: [{ id: 1813, name: 'tracker.example.com' }],
  groups: [{ id: 10332, name: 'FORTESTS' }, { id: 10333, name: 'Other' }],
  trafficSources: [{ id: 836, name: 'FORTESTS' }],
  countries: [{ id: 'AU', name: 'Австралия' }, { id: 'KZ', name: 'Казахстан' }],
}
const OFFERS = [{ id: 11111, name: 'Offer A' }, { id: 11112, name: 'Offer B' }]

function form(props: Record<string, unknown> = {}) {
  return mount(CreatorForm, { props: { options: OPTIONS, offers: OFFERS, ...props }, attachTo: document.body })
}

function control(wrapper: VueWrapper, label: string) {
  const caption = wrapper.findAll('label').find(item => item.text() === label)
  if (!caption) throw new Error(`no field labelled ${label}`)
  return wrapper.get(`[id="${caption.attributes('for')}"]`)
}

async function pick(wrapper: VueWrapper, label: string, text: string) {
  const input = control(wrapper, label)
  await input.setValue(text)
  await input.trigger('keydown', { key: 'Enter' })
}

function errorAt(wrapper: VueWrapper, label: string): string | undefined {
  const id = control(wrapper, label).attributes('aria-describedby')?.split(' ').find(item => item.endsWith('-error'))
  return id ? wrapper.get(`[id="${id}"]`).text() : undefined
}

async function fill(wrapper: VueWrapper) {
  await control(wrapper, 'Название').setValue('au_flexacil')
  await pick(wrapper, 'Страна', 'au')
  await pick(wrapper, 'Оффер', 'offer')
  await pick(wrapper, 'Группа', 'fortests')
}

describe('CreatorForm', () => {
  it('sends the name with the fixed prefix and every chosen reference (R-UX-01, R-UX-02)', async () => {
    const wrapper = form()

    await fill(wrapper)
    await wrapper.get('form').trigger('submit')

    expect(wrapper.text()).toContain('test_bulygin_')
    expect(wrapper.emitted('submit')).toEqual([[{
      name: 'test_bulygin_au_flexacil',
      country: 'AU',
      offerId: 11111,
      groupId: 10332,
      trafficSourceId: 836,
      domainId: 1813,
    }]])
  })

  it('chooses for the user where there is nothing to choose from', () => {
    const wrapper = form()

    expect((control(wrapper, 'Домен').element as HTMLInputElement).value).toBe('tracker.example.com')
    expect((control(wrapper, 'Источник трафика').element as HTMLInputElement).value).toBe('FORTESTS')
    expect((control(wrapper, 'Группа').element as HTMLInputElement).value).toBe('')
  })

  it('names every empty field and sends nothing (R-UX-03)', async () => {
    const wrapper = form()

    await wrapper.get('form').trigger('submit')

    expect(wrapper.emitted('submit')).toBeUndefined()
    expect(errorAt(wrapper, 'Название')).toBe('Введите продолжение названия')
    expect(errorAt(wrapper, 'Страна')).toBe('Выберите страну')
    expect(errorAt(wrapper, 'Оффер')).toBe('Выберите оффер')
    expect(errorAt(wrapper, 'Группа')).toBe('Выберите группу')
    expect(errorAt(wrapper, 'Домен')).toBeUndefined()
  })

  it('shows a remark of the server at its field until the field is changed (R-UX-03)', async () => {
    const wrapper = form()
    await fill(wrapper)

    await wrapper.setProps({
      remarks: [
        { field: 'offerId', message: 'В Keitaro нет активного оффера с таким ID' },
        { field: 'newDomainName', message: 'Имя хоста без схемы и пути' },
      ],
    })
    expect(errorAt(wrapper, 'Оффер')).toBe('В Keitaro нет активного оффера с таким ID')
    expect(errorAt(wrapper, 'Домен')).toBe('Имя хоста без схемы и пути')

    const offer = control(wrapper, 'Оффер')
    await offer.trigger('focus')
    await offer.trigger('keydown', { key: 'ArrowDown' })
    await offer.trigger('keydown', { key: 'Enter' })
    expect(errorAt(wrapper, 'Оффер')).toBeUndefined()
    expect(errorAt(wrapper, 'Домен')).toBe('Имя хоста без схемы и пути')
  })

  it('puts a refusal about no field above the form (R-UX-03)', () => {
    const wrapper = form({ failure: 'Keitaro не создал поток. Кампания удалена.' })

    const alert = wrapper.get('[role="alert"]')
    expect(alert.text()).toContain('Кампания не создана')
    expect(alert.text()).toContain('Keitaro не создал поток. Кампания удалена.')
  })

  it('offers to create a domain and creates it only on submit (R-UX-05)', async () => {
    const wrapper = form()
    await fill(wrapper)

    const domain = control(wrapper, 'Домен')
    await domain.setValue('New.Example.com')
    expect(wrapper.findAll('[role="option"]').some(item => item.text() === 'Создать домен new.example.com')).toBe(true)
    await domain.trigger('keydown', { key: 'Enter' })

    expect((domain.element as HTMLInputElement).value).toBe('new.example.com')
    expect(wrapper.text()).toContain('Новый домен: будет создан в Keitaro при отправке формы')
    expect(wrapper.emitted('submit')).toBeUndefined()

    await wrapper.get('form').trigger('submit')
    const sent = wrapper.emitted('submit')?.[0]?.[0]
    expect(sent).toMatchObject({ newDomainName: 'new.example.com' })
    expect(sent).not.toHaveProperty('domainId')
  })

  it('asks the page to search offers as the user types (R-UX-02)', async () => {
    const wrapper = form()

    await control(wrapper, 'Оффер').setValue('flex')

    expect(wrapper.emitted('search-offers')).toEqual([['flex']])
  })

  it('cannot be sent twice while the request runs', () => {
    const wrapper = form({ busy: true })

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
  })
})

describe('CreatorResult', () => {
  it('leads to the editor and to the tracker (R-UX-04)', async () => {
    const wrapper = mount(CreatorResult, {
      props: {
        campaign: {
          id: 'c-1',
          keitaroId: 93212,
          name: 'test_bulygin_au',
          alias: 'alias001',
          country: 'AU',
          trackerLink: 'https://tracker.test/admin/#!/campaigns/93212',
        },
      },
    })
    const links = Object.fromEntries(wrapper.findAll('a').map(link => [link.text(), link.attributes('href')]))

    expect(wrapper.text()).toContain('test_bulygin_au')
    expect(wrapper.text()).toContain('93212')
    expect(links['В редактор']).toBe('/campaigns/c-1')
    expect(links['Открыть в Keitaro (в новой вкладке)']).toBe('https://tracker.test/admin/#!/campaigns/93212')

    await wrapper.get('button').trigger('click')
    expect(wrapper.emitted('again')).toHaveLength(1)
  })
})
