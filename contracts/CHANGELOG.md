# Changelog

Версия одна для npm-пакета и пакета Python. Удаление или переименование — мажорная, добавление — минорная. До версии 1.0.0 ломающее изменение поднимает минорную версию и помечено словом «Ломающее».

## 0.11.0

- `retryTask` повторяет и отклонённое создание кампании; в `RetryTaskResult` добавлены `ValidationFailed` и `KeitaroFailure` — исчерпывающий разбор результата у потребителя нужно дополнить.

## 0.10.0

- **Ломающее.** `createCampaign` ставит задачу: во входе обязательное `CreateCampaignInput.taskId`, результат — `CreateCampaignResult = Task | ValidationFailed | KeitaroFailure | TaskKeyReused` (вариант `Campaign` убран). Созданная кампания — в `Task.campaignId` завершённой задачи.

## 0.9.0

- Запросы `tasks(statuses, kind, first)` и `queueStatus`; типы `QueueStatus`, `QueueState`, `TaskCount`.
- Мутации `cancelTask(id)` → `CancelTaskResult = Task | TaskNotFound | TaskNotCancellable` и `retryTask(input: RetryTaskInput!)` → `RetryTaskResult = Task | TaskNotFound | TaskNotRetryable | StreamBusy | StreamNotFound | EmptyStream | TaskKeyReused`.
- Поле `Task.retryOf`.

## 0.8.0

- **Ломающее.** Мутация `pushStream` удалена. Вместо неё `publishStream(input: PublishStreamInput!)`: ставит задачу и возвращает `PublishStreamResult = Task | StreamConflict | StreamBusy | StreamNotFound | EmptyStream | TaskKeyReused`.
- **Ломающее.** Из `StreamResult` убран `EmptyStream`, добавлен `StreamBusy`; в `FetchStreamsResult` добавлен `StreamBusy`.
- Типы `Task`, `TaskStep`, `TaskRefusal`, `TaskKeyReused`, enum `TaskKind`, `TaskStatus`; запрос `task(id)`.
- Поле `Stream.publishingTaskId`.

## 0.7.0

- Поле `Stream.version` — номер записи потока.
- Необязательное `expectedVersion` во входах `StreamOfferInput`, `PinShareInput` и аргументом у `cancelDraft`, `pushStream`.
- В `StreamResult` добавлен вариант `StreamConflict { message, stream }` — исчерпывающий разбор результата у потребителя нужно дополнить.

## 0.6.0

- Запрос `serviceInfo` и тип `ServiceInfo`: префикс названий кампаний и адрес трекера.

## 0.5.0

- Мутация `pushStream(streamId)`.
- В `StreamResult` добавлен вариант `EmptyStream` — исчерпывающий разбор результата у потребителя нужно дополнить.

## 0.4.0

- Мутации черновика: `addOffer`, `removeOffer`, `bringBackOffer`, `pinShare`, `unpinShare`, `cancelDraft`.
- Результат `StreamResult = Stream | StreamNotFound | OfferNotFound | OfferAlreadyInStream | ShareOverflow | ValidationFailed | KeitaroFailure`.
- Входные типы `StreamOfferInput`, `PinShareInput`.

## 0.3.0

- Типы редактора: `Stream`, `StreamOffer`, `PublishedOffer`, enum `OfferState`.
- Запросы `campaigns`, `campaign(id)`, `streams(campaignId)`.
- Мутация `fetchStreams(campaignKeitaroId)` с результатом `FetchStreamsResult = StreamsFetched | DraftNotPublished | CampaignNotFound | KeitaroFailure`.

## 0.2.0

- Мутация `createCampaign(input)` с результатом `CreateCampaignResult = Campaign | ValidationFailed | KeitaroFailure`.
- Типы `Campaign`, `CreateCampaignInput`, `FieldError`, `ValidationFailed`, `KeitaroFailure`.

## 0.1.0

- Справочники: `Domain`, `Group`, `TrafficSource`, `Offer`, `Country`.
- Запросы: `domains`, `groups`, `trafficSources`, `offers(search, limit)`, `countries(search)`.
