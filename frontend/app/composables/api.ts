import type { ApiError } from '../../shared/types/api'

const FALLBACK = 'Не удалось выполнить запрос. Проверьте соединение и повторите.'

/** Read the refusal the BFF sent; anything else means the request did not get through. */
export function toApiError(error: unknown): ApiError {
  const body = (error as { data?: { data?: unknown } } | null)?.data?.data
  if (body && typeof body === 'object' && 'code' in body && 'message' in body) return body as ApiError
  return { code: 'network', message: FALLBACK }
}

export interface ApiRequest {
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE'
  body?: unknown
  query?: Record<string, string | number>
}

/**
 * Call the BFF. The answer type is named by the caller: letting TypeScript match the address
 * against every route of the server is too deep for the compiler.
 */
export function api<T>(url: string, request: ApiRequest = {}): Promise<T> {
  const send = $fetch as unknown as (url: string, request: ApiRequest) => Promise<T>
  return send(url, request)
}
