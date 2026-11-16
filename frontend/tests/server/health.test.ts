import { describe, expect, it } from 'vitest'
import { buildHealth } from '../../server/utils/health'

describe('health', () => {
  it('reports ok', () => {
    expect(buildHealth()).toEqual({ status: 'ok' })
  })
})
