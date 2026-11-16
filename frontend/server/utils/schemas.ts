import * as v from 'valibot'
import type { FieldRemark } from './api-error'
import { fail } from './api-error'

const id = v.pipe(v.number(), v.integer(), v.minValue(1))
/** A whole number that may arrive as text: route parameters and query strings are strings. */
const idLike = v.pipe(
  v.union([v.number(), v.pipe(v.string(), v.regex(/^\d+$/), v.transform(Number))]),
  v.integer(),
  v.minValue(1),
)
const text = v.pipe(v.string(), v.trim(), v.minLength(1))

export const campaignInput = v.object({
  name: text,
  country: text,
  offerId: id,
  groupId: id,
  trafficSourceId: id,
  domainId: v.optional(id),
  newDomainName: v.optional(text),
})
export const offerSearch = v.object({ search: v.optional(v.pipe(v.string(), v.trim()), '') })
export const fetchInput = v.object({ keitaroId: idLike })
export const streamRef = v.object({ streamId: text })
export const offerRef = v.object({ streamId: text, offerId: idLike })
export const offerBody = v.object({ offerId: id })
/** The range of a share is a rule of the domain, so only the type is checked here. */
export const shareBody = v.object({ share: v.pipe(v.number(), v.integer()) })

/** Check the form of the input; what it means is the backend's business (R-ARCH-05). */
export function parse<TSchema extends v.GenericSchema>(schema: TSchema, value: unknown): v.InferOutput<TSchema> {
  const result = v.safeParse(schema, value ?? {})
  if (result.success) return result.output
  const fields: FieldRemark[] = result.issues.map(issue => ({
    field: issue.path?.map(item => String(item.key)).join('.') ?? '',
    message: issue.message,
  }))
  fail(400, 'invalid_input', 'Запрос составлен неверно', fields)
}
