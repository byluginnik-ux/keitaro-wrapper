# Changelog

Версия одна для npm-пакета и пакета Python. Удаление или переименование — мажорная, добавление — минорная.

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
