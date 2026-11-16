// @vitest-environment happy-dom
import type { VueWrapper } from '@vue/test-utils'
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import OfferRow from '../../app/components/editor/OfferRow.vue'
import ShareBar from '../../app/components/editor/ShareBar.vue'
import StreamCard from '../../app/components/editor/StreamCard.vue'
import type { OfferView, StreamView } from '../../shared/types/api'

function offer(patch: Partial<OfferView> = {}): OfferView {
  return {
    offerId: 11111,
    name: 'Offer A',
    share: 34,
    pinned: false,
    removed: false,
    isNew: false,
    changed: false,
    publishedShare: 34,
    ...patch,
  }
}

function stream(patch: Partial<StreamView> = {}): StreamView {
  return {
    id: 's-2',
    keitaroId: 564221,
    name: 'Flow 2',
    position: 2,
    acceptsOffers: true,
    dirty: false,
    changes: 0,
    total: 100,
    offers: [
      offer(),
      offer({ offerId: 11112, name: 'Offer B', share: 33, publishedShare: 33 }),
      offer({ offerId: 11113, name: 'Offer C', share: 33, publishedShare: 33 }),
    ],
    ...patch,
  }
}

const FOUND = [{ id: 11111, name: 'Offer A' }, { id: 11114, name: 'Offer D' }]

function row(patch: Partial<OfferView> = {}, props: Record<string, unknown> = {}) {
  return mount(OfferRow, { props: { offer: offer(patch), ...props }, attachTo: document.body })
}

function card(patch: Partial<StreamView> = {}, props: Record<string, unknown> = {}) {
  return mount(StreamCard, { props: { stream: stream(patch), offers: FOUND, ...props }, attachTo: document.body })
}

function button(wrapper: VueWrapper, name: string | RegExp) {
  const found = wrapper.findAll('button').find((item) => {
    const label = item.attributes('aria-label') ?? item.text()
    return typeof name === 'string' ? label === name : name.test(label)
  })
  if (!found) throw new Error(`no button named ${name}`)
  return found
}

function names(wrapper: VueWrapper): string[] {
  return wrapper.findAll('button').map(item => item.attributes('aria-label') ?? item.text())
}

describe('ShareBar', () => {
  it('has a text alternative that lists active offers with their shares (R-UX-10)', () => {
    const wrapper = mount(ShareBar, {
      props: { total: 100, offers: [offer({ share: 60 }), offer({ offerId: 2, name: 'Offer B', share: 0, removed: true }), offer({ offerId: 3, name: 'Offer C', share: 40 })] },
    })

    expect(wrapper.get('[role="img"]').attributes('aria-label')).toBe('Доли офферов: Offer A — 60 %; Offer C — 40 %')
    expect(wrapper.text()).toBe('Сумма 100 %')
  })
})

describe('OfferRow', () => {
  it('shows an active offer with its share and what can be done to it (R-UX-10)', () => {
    const wrapper = row()

    expect(wrapper.text()).toContain('Offer A')
    expect(wrapper.text()).toContain('34 %')
    expect(wrapper.text()).not.toContain('→')
    expect(names(wrapper)).toEqual([
      'Доля оффера Offer A: 34 %. Изменить',
      'Закрепить долю: Offer A',
      'Удалить Offer A',
    ])
  })

  it('marks a removed offer with a label and offers only to bring it back (R-UX-11)', async () => {
    const wrapper = row({ removed: true, share: 0, changed: true, publishedShare: 33 })

    expect(wrapper.text()).toContain('Удалён')
    expect(wrapper.text()).toContain('0 %')
    expect(names(wrapper)).toEqual(['Вернуть Offer A'])

    await button(wrapper, 'Вернуть Offer A').trigger('click')
    expect(wrapper.emitted('restore')).toHaveLength(1)
  })

  it('names a pinned share for a screen reader, not by colour alone (R-UX-11)', async () => {
    const wrapper = row({ pinned: true })
    const pin = button(wrapper, 'Доля закреплена: Offer A. Открепить')

    expect(pin.attributes('aria-pressed')).toBe('true')
    await pin.trigger('click')
    expect(wrapper.emitted('unpin')).toHaveLength(1)
  })

  it('pins the current share from the pin button', async () => {
    const wrapper = row()
    const pin = button(wrapper, 'Закрепить долю: Offer A')

    expect(pin.attributes('aria-pressed')).toBe('false')
    await pin.trigger('click')
    expect(wrapper.emitted('pin')).toEqual([[34]])
  })

  it('shows what a changed share was and what it became (R-UX-12)', () => {
    const wrapper = row({ share: 25, publishedShare: 33, changed: true })

    expect(wrapper.text().replace(/\s+/g, ' ')).toContain('Было 33 → , стало 25 %')
  })

  it('marks an offer that was never published', () => {
    const wrapper = row({ isNew: true, changed: true, publishedShare: null })

    expect(wrapper.text()).toContain('Новый')
    expect(wrapper.text()).not.toContain('→')
  })

  it('edits the share in place: Enter pins the value (R-UX-14)', async () => {
    const wrapper = row()

    await button(wrapper, /Изменить$/).trigger('click')
    const input = wrapper.get('input')
    expect(input.attributes('aria-label')).toBe('Доля оффера Offer A, %')
    expect(input.element.value).toBe('34')
    await input.setValue('50')
    await input.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('pin')).toEqual([[50]])
    expect(wrapper.find('input').exists()).toBe(false)
  })

  it('takes the focus back to the share once the request is over (R-UX-15)', async () => {
    const wrapper = row()

    await button(wrapper, /Изменить$/).trigger('click')
    await wrapper.get('input').setValue('50')
    await wrapper.get('input').trigger('keydown', { key: 'Enter' })
    await wrapper.setProps({ locked: true })
    ;(document.activeElement as HTMLElement | null)?.blur()
    await wrapper.setProps({ locked: false, offer: offer({ share: 50, pinned: true }) })
    await wrapper.vm.$nextTick()

    expect(document.activeElement).toBe(button(wrapper, /^Доля оффера Offer A: 50 %/).element)
  })

  it('edits the share in place: Esc drops the input (R-UX-14)', async () => {
    const wrapper = row()

    await button(wrapper, /Изменить$/).trigger('click')
    await wrapper.get('input').setValue('50')
    await wrapper.get('input').trigger('keydown', { key: 'Escape' })

    expect(wrapper.emitted('pin')).toBeUndefined()
    expect(wrapper.find('input').exists()).toBe(false)
    expect(document.activeElement).toBe(button(wrapper, /Изменить$/).element)
  })

  it('does not send a share that is not a whole number', async () => {
    const wrapper = row()

    await button(wrapper, /Изменить$/).trigger('click')
    await wrapper.get('input').setValue('12.5')
    await wrapper.get('input').trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('pin')).toBeUndefined()
    expect(wrapper.get('input').attributes('aria-invalid')).toBe('true')
  })

  it('cannot be acted on while a request of its stream runs (R-UX-16)', () => {
    const wrapper = row({}, { locked: true })

    expect(wrapper.findAll('button').every(item => item.attributes('disabled') !== undefined)).toBe(true)
  })
})

describe('StreamCard', () => {
  it('shows the name, the share scale and the offers of a published stream (R-UX-10)', () => {
    const wrapper = card()

    expect(wrapper.get('h2').text()).toBe('Flow 2')
    expect(wrapper.find('[role="img"]').exists()).toBe(true)
    expect(wrapper.findAll('li.row')).toHaveLength(3)
    expect(wrapper.text()).not.toContain('Не опубликовано')
    expect(names(wrapper)).not.toContain('Опубликовать')
  })

  it('labels a draft and counts its changes in the publish panel (R-UX-11, R-UX-13)', async () => {
    const wrapper = card({ dirty: true, changes: 2 })

    expect(wrapper.text()).toContain('Не опубликовано')
    expect(wrapper.get('footer').text()).toContain('Изменений: 2')

    await button(wrapper, 'Опубликовать').trigger('click')
    await button(wrapper, 'Отменить').trigger('click')
    expect(wrapper.emitted('command')).toEqual([[{ action: 'push' }], [{ action: 'cancel' }]])
  })

  it('shows a redirect stream without contents and without adding (R-UX-16)', () => {
    const wrapper = card({ acceptsOffers: false, offers: [], total: 0, name: 'Flow 1' })

    expect(wrapper.text()).toContain('Поток без офферов')
    expect(wrapper.find('[role="combobox"]').exists()).toBe(false)
    expect(wrapper.findAll('button')).toHaveLength(0)
  })

  it('invites to add the first offer to an empty stream (R-UX-16)', () => {
    const wrapper = card({ offers: [], total: 0 })

    expect(wrapper.text()).toContain('В потоке нет офферов')
    expect(wrapper.find('[role="img"]').exists()).toBe(false)
    expect(wrapper.find('[role="combobox"]').exists()).toBe(true)
  })

  it('adds a found offer and refuses one that is already in the stream', async () => {
    const wrapper = card()
    const input = wrapper.get('[role="combobox"]')

    await input.setValue('off')
    expect(wrapper.emitted('search-offers')).toEqual([['off']])
    const options = wrapper.findAll('[role="option"]')
    expect(options[0]?.attributes('aria-disabled')).toBe('true')
    expect(options[0]?.text()).toContain('уже в потоке')

    await options[0]?.trigger('click')
    expect(wrapper.emitted('command')).toBeUndefined()
    await options[1]?.trigger('click')
    expect(wrapper.emitted('command')).toEqual([[{ action: 'add', offerId: 11114 }]])
  })

  it('passes on what was asked of an offer', async () => {
    const wrapper = card()

    await button(wrapper, 'Удалить Offer B').trigger('click')
    await button(wrapper, 'Закрепить долю: Offer C').trigger('click')

    expect(wrapper.emitted('command')).toEqual([
      [{ action: 'remove', offerId: 11112 }],
      [{ action: 'pin', offerId: 11113, share: 33 }],
    ])
  })

  it('shows a refusal and keeps the draft on the screen (R-UX-16)', () => {
    const wrapper = card({ dirty: true, changes: 1 }, { error: 'Keitaro ответил 500. Черновик сохранён.' })

    expect(wrapper.get('[role="alert"]').text()).toContain('Keitaro ответил 500. Черновик сохранён.')
    expect(wrapper.findAll('li.row')).toHaveLength(3)
    expect(wrapper.get('footer').text()).toContain('Изменений: 1')
  })

  it('returns the focus to the pressed control when the answer comes (R-UX-15)', async () => {
    const wrapper = card()
    const pin = button(wrapper, 'Закрепить долю: Offer C')
    ;(pin.element as HTMLElement).focus()

    await wrapper.setProps({ pending: 'pin' })
    ;(document.activeElement as HTMLElement | null)?.blur()
    await wrapper.setProps({ pending: null })
    await wrapper.vm.$nextTick()

    expect(document.activeElement).toBe(pin.element)
  })

  it('keeps the focus in the stream when the pressed control is gone (R-UX-15)', async () => {
    const wrapper = card({ dirty: true, changes: 1 })
    const push = button(wrapper, 'Опубликовать')
    ;(push.element as HTMLElement).focus()

    await wrapper.setProps({ pending: 'push' })
    ;(document.activeElement as HTMLElement | null)?.blur()
    await wrapper.setProps({ pending: null, stream: stream() })
    await wrapper.vm.$nextTick()

    expect(document.activeElement).toBe(wrapper.element)
  })

  it('locks its buttons while a request runs and marks the pressed one (R-UX-16)', () => {
    const wrapper = card({ dirty: true, changes: 1 }, { pending: 'push' })

    expect(wrapper.findAll('button').every(item => item.attributes('disabled') !== undefined)).toBe(true)
    expect(button(wrapper, /Опубликовать/).attributes('aria-busy')).toBe('true')
    expect(button(wrapper, /Отменить/).attributes('aria-busy')).toBeUndefined()
  })
})
