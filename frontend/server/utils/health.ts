export interface Health {
  status: 'ok'
}

export function buildHealth(): Health {
  return { status: 'ok' }
}
