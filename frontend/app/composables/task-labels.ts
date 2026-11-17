/** What the steps of a task are called on the screen; an unknown step shows its own name. */
export const STEP_LABELS: Record<string, string> = {
  'queued': 'Поставлена',
  'attempt': 'Попытка',
  'published': 'Опубликовано',
  'domain': 'Домен готов',
  'campaign': 'Кампания создана в Keitaro',
  'created': 'Потоки созданы, кампания сохранена',
  'rejected': 'Отклонена',
  'cancelled': 'Отменена',
  'nothing to publish': 'Изменений нет',
}

export function stepLabel(name: string): string {
  return STEP_LABELS[name] ?? name
}
