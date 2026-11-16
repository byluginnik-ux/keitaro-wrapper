// @vitest-environment happy-dom
import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import ThemeToggle from '../../app/components/ui/ThemeToggle.vue'
import UiButton from '../../app/components/ui/UiButton.vue'
import UiCombobox from '../../app/components/ui/UiCombobox.vue'
import UiField from '../../app/components/ui/UiField.vue'
import UiNotice from '../../app/components/ui/UiNotice.vue'

const OPTIONS = [
  { id: 1, name: 'Offer Alpha' },
  { id: 2, name: 'Offer Beta' },
  { id: 30, name: 'Gamma' },
]

function combobox(props: Record<string, unknown> = {}) {
  const wrapper = mount(UiCombobox, {
    props: { label: 'Оффер', options: OPTIONS, modelValue: null, ...props },
    attachTo: document.body,
  })
  const input = wrapper.get('input[role="combobox"]')
  const names = () => wrapper.findAll('[role="option"]').map(item => item.text())
  return { wrapper, input, names }
}

describe('UiButton', () => {
  it('is unavailable and announced as busy while its request runs (R-UX-16)', () => {
    const wrapper = mount(UiButton, { props: { busy: true }, slots: { default: 'Опубликовать' } })

    expect(wrapper.attributes('disabled')).toBeDefined()
    expect(wrapper.attributes('aria-busy')).toBe('true')
    expect(wrapper.text()).toContain('Опубликовать')
  })

  it('does not submit a form unless asked to', () => {
    expect(mount(UiButton).attributes('type')).toBe('button')
  })
})

describe('UiField', () => {
  it('ties the label, the fixed prefix and the error to the input (R-UX-01, R-UX-03)', () => {
    const wrapper = mount(UiField, {
      props: { label: 'Название', modelValue: 'au', prefix: 'test_bulygin_', error: 'Слишком коротко' },
    })
    const input = wrapper.get('input')

    expect(wrapper.get('label').attributes('for')).toBe(input.attributes('id'))
    expect(input.element.value).toBe('au')
    expect(input.attributes('aria-invalid')).toBe('true')
    const described = input.attributes('aria-describedby')?.split(' ') ?? []
    expect(described.map(id => wrapper.get(`[id="${id}"]`).text())).toEqual(['test_bulygin_', 'Слишком коротко'])
  })

  it('reports what the user types, never the prefix', async () => {
    const wrapper = mount(UiField, { props: { label: 'Название', modelValue: '', prefix: 'test_bulygin_' } })

    await wrapper.get('input').setValue('kz_offer')

    expect(wrapper.emitted('update:modelValue')).toEqual([['kz_offer']])
  })
})

describe('UiNotice', () => {
  it('interrupts the reader only for a refusal', () => {
    expect(mount(UiNotice, { props: { tone: 'risk' } }).attributes('role')).toBe('alert')
    expect(mount(UiNotice).attributes('role')).toBe('status')
  })
})

describe('UiCombobox', () => {
  it('filters by name and by the start of the identifier (R-UX-02)', async () => {
    const { input, names } = combobox({ showId: true })

    await input.setValue('beta')
    expect(names()).toEqual(['Offer Beta2'])

    await input.setValue('3')
    expect(names()).toEqual(['Gamma30'])
  })

  it('is chosen from the keyboard alone (R-UX-15)', async () => {
    const { wrapper, input } = combobox()

    await input.trigger('focus')
    expect(input.attributes('aria-expanded')).toBe('true')
    await input.trigger('keydown', { key: 'ArrowDown' })
    expect(input.attributes('aria-activedescendant')).toBe(wrapper.findAll('[role="option"]')[1]?.attributes('id'))
    await input.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('update:modelValue')).toEqual([[OPTIONS[1]]])
    expect(input.attributes('aria-expanded')).toBe('false')
  })

  it('restores the chosen name when the list is left with Escape', async () => {
    const { wrapper, input } = combobox({ modelValue: OPTIONS[0] })

    await input.setValue('zzz')
    await input.trigger('keydown', { key: 'Escape' })

    expect((input.element as HTMLInputElement).value).toBe('Offer Alpha')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('says so when nothing matches', async () => {
    const { wrapper, input } = combobox()

    await input.setValue('zzz')

    expect(wrapper.get('[role="listbox"]').text()).toBe('Ничего не найдено')
  })

  it('lists an unavailable option with the reason and does not choose it', async () => {
    const { wrapper, input } = combobox({ disabledIds: [1], disabledNote: 'уже в потоке' })

    await input.trigger('focus')
    const first = wrapper.findAll('[role="option"]')[0]
    await first?.trigger('click')

    expect(first?.attributes('aria-disabled')).toBe('true')
    expect(first?.text()).toContain('уже в потоке')
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()
  })

  it('offers to create what is not in the list (R-UX-05)', async () => {
    const { wrapper, input, names } = combobox({ createLabel: (text: string) => `Создать домен ${text}` })

    await input.setValue(' new.example.com ')
    expect(names()).toEqual(['Создать домен new.example.com'])
    await input.trigger('keydown', { key: 'Enter' })

    expect(wrapper.emitted('create')).toEqual([['new.example.com']])
  })

  it('does not offer to create a name that already exists', async () => {
    const { input, names } = combobox({ createLabel: (text: string) => `Создать ${text}` })

    await input.setValue('gamma')

    expect(names()).toEqual(['Gamma'])
  })

  it('leaves the search to the server when told so', async () => {
    const { wrapper, input, names } = combobox({ remote: true })

    await input.setValue('flex')

    expect(wrapper.emitted('search')).toEqual([['flex']])
    expect(names()).toHaveLength(3)
  })

  it('does not choose from a list the server is still replacing', async () => {
    const { wrapper, input } = combobox({ remote: true, loading: true })

    await input.setValue('flex')
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toBeUndefined()

    await wrapper.setProps({ loading: false })
    await input.trigger('keydown', { key: 'Enter' })
    expect(wrapper.emitted('update:modelValue')).toEqual([[OPTIONS[0]]])
  })

  it('clears the choice when the text is erased', async () => {
    const { wrapper, input } = combobox({ modelValue: OPTIONS[0] })

    await input.setValue('')

    expect(wrapper.emitted('update:modelValue')).toEqual([[null]])
  })
})

describe('ThemeToggle', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.mode
  })

  it('goes from the system theme to light, to dark and back (R-UX-20)', async () => {
    const wrapper = mount(ThemeToggle)
    expect(wrapper.text()).toContain('как в системе')

    await wrapper.trigger('click')
    expect(document.documentElement.dataset.mode).toBe('light')
    expect(wrapper.text()).toContain('светлая')

    await wrapper.trigger('click')
    expect(document.documentElement.dataset.mode).toBe('dark')
    expect(localStorage.getItem('theme-mode')).toBe('dark')

    await wrapper.trigger('click')
    expect(document.documentElement.dataset.mode).toBeUndefined()
    expect(localStorage.getItem('theme-mode')).toBeNull()
  })

  it('remembers the choice on the next visit', async () => {
    localStorage.setItem('theme-mode', 'dark')

    const wrapper = mount(ThemeToggle)
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('тёмная')
  })
})
