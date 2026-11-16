import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = readFileSync(new URL('../../app/assets/styles/tokens.css', import.meta.url), 'utf8')

type Theme = 'light' | 'dark'

function token(name: string, theme: Theme): string {
  const match = css.match(new RegExp(`--${name}:\\s*light-dark\\((#[0-9a-f]{6}),\\s*(#[0-9a-f]{6})\\)`, 'i'))
  if (!match?.[1] || !match[2]) throw new Error(`token --${name} is not a pair of hex colours`)
  return theme === 'light' ? match[1] : match[2]
}

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((start) => {
    const channel = Number.parseInt(hex.slice(start, start + 2), 16) / 255
    return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4
  }) as [number, number, number]
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(foreground: string, background: string): number {
  const [light, dark] = [luminance(foreground), luminance(background)].sort((a, b) => b - a) as [number, number]
  return (light + 0.05) / (dark + 0.05)
}

const TEXT_PAIRS = [
  ['ink', 'ground'],
  ['ink', 'mist'],
  ['ink', 'mist-2'],
  ['cap', 'ground'],
  ['cap', 'mist'],
  ['acc-text', 'ground'],
  ['acc-text', 'mist'],
  ['risk-text', 'ground'],
  ['risk-text', 'mist'],
  ['ink', 'acc'],
  ['ink', 'risk'],
  ['ground', 'ink'],
] as const
const CONTROL_PAIRS = [
  ['line', 'ground'],
  ['line', 'mist'],
  ['acc-line', 'ground'],
  ['acc-line', 'mist'],
  ['risk-deep', 'ground'],
] as const

describe.each(['light', 'dark'] as const)('%s theme (R-UX-22)', (theme) => {
  it.each(TEXT_PAIRS)('text --%s on --%s reaches AA 4.5', (foreground, background) => {
    expect(contrast(token(foreground, theme), token(background, theme))).toBeGreaterThanOrEqual(4.5)
  })

  it.each(CONTROL_PAIRS)('control --%s on --%s reaches AA 3', (foreground, background) => {
    expect(contrast(token(foreground, theme), token(background, theme))).toBeGreaterThanOrEqual(3)
  })
})

describe('tokens', () => {
  it('follow the system and obey the manual switch (R-UX-20)', () => {
    expect(css).toMatch(/:root\s*{\s*color-scheme:\s*light dark/)
    expect(css).toMatch(/:root\[data-mode="light"\]\s*{\s*color-scheme:\s*light;/)
    expect(css).toMatch(/:root\[data-mode="dark"\]\s*{\s*color-scheme:\s*dark;/)
  })
})
