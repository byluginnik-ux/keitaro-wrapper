// GENERATED from schema.graphql by scripts/generate.sh — do not edit by hand.
export type Maybe<T> = T | null;
export type InputMaybe<T> = Maybe<T>;
/** All built-in and custom scalars, mapped to their actual values */
export type Scalars = {
  ID: { input: string; output: string; }
  String: { input: string; output: string; }
  Boolean: { input: boolean; output: boolean; }
  Int: { input: number; output: number; }
  Float: { input: number; output: number; }
};

/** Кампания, которую ведёт сервис */
export type Campaign = {
  __typename?: 'Campaign';
  /** Псевдоним в адресе кампании */
  alias: Scalars['String']['output'];
  /** Код страны alpha-2, заданный при создании */
  country?: Maybe<Scalars['String']['output']>;
  /** Наш идентификатор */
  id: Scalars['ID']['output'];
  /** Идентификатор кампании в Keitaro */
  keitaroId: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** В Keitaro нет кампании с таким ID */
export type CampaignNotFound = {
  __typename?: 'CampaignNotFound';
  message: Scalars['String']['output'];
};

export type CancelTaskResult = Task | TaskNotCancellable | TaskNotFound;

/** Страна ISO 3166-1 */
export type Country = {
  __typename?: 'Country';
  /** Код alpha-2 в верхнем регистре */
  code: Scalars['String']['output'];
  name: Scalars['String']['output'];
};

/** Что создать: кампания с двумя потоками */
export type CreateCampaignInput = {
  /** Код страны alpha-2: её посетителей первый поток уводит на Google */
  country: Scalars['String']['input'];
  /** Существующий домен. Задаётся ровно одно из двух: domainId или newDomainName */
  domainId?: InputMaybe<Scalars['Int']['input']>;
  groupId: Scalars['Int']['input'];
  /** Название с обязательным префиксом тестовых кампаний */
  name: Scalars['String']['input'];
  /** Имя хоста нового домена: он создаётся в Keitaro перед кампанией */
  newDomainName?: InputMaybe<Scalars['String']['input']>;
  /** Оффер второго потока */
  offerId: Scalars['Int']['input'];
  /** Идентификатор новой задачи (UUID); повтор с ним же вернёт ту же задачу */
  taskId: Scalars['ID']['input'];
  trafficSourceId: Scalars['Int']['input'];
};

export type CreateCampaignResult = KeitaroFailure | Task | TaskKeyReused | ValidationFailed;

/** Домен трекера, на котором размещается кампания */
export type Domain = {
  __typename?: 'Domain';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** В кампании есть неопубликованный черновик: его нужно опубликовать или отменить */
export type DraftNotPublished = {
  __typename?: 'DraftNotPublished';
  message: Scalars['String']['output'];
};

/** В потоке нет активных офферов: публиковать нечего */
export type EmptyStream = {
  __typename?: 'EmptyStream';
  message: Scalars['String']['output'];
};

export type FetchStreamsResult = CampaignNotFound | DraftNotPublished | KeitaroFailure | StreamBusy | StreamsFetched;

/** Замечание к одному полю ввода */
export type FieldError = {
  __typename?: 'FieldError';
  /** Имя поля входного типа */
  field: Scalars['String']['output'];
  message: Scalars['String']['output'];
};

/** Группа кампаний */
export type Group = {
  __typename?: 'Group';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** Keitaro отказал или не ответил; незавершённых кампаний в трекере не оставлено */
export type KeitaroFailure = {
  __typename?: 'KeitaroFailure';
  /** Домен, который успел создаться до сбоя и остался в трекере */
  createdDomain?: Maybe<Domain>;
  message: Scalars['String']['output'];
};

export type Mutation = {
  __typename?: 'Mutation';
  /** Добавить оффер в черновик потока; убранный оффер возвращается */
  addOffer: StreamResult;
  /** Вернуть убранный оффер */
  bringBackOffer: StreamResult;
  /** Отменить черновик: поток возвращается к опубликованному снимку */
  cancelDraft: StreamResult;
  /** Отменить задачу, за которую обработчик ещё не взялся; поток освобождается */
  cancelTask: CancelTaskResult;
  /** Создать кампанию: поток 1 уводит страну на Google, поток 2 ведёт на оффер */
  createCampaign: CreateCampaignResult;
  /** Загрузить потоки кампании из Keitaro по её ID в трекере и сверить с сохранёнными */
  fetchStreams: FetchStreamsResult;
  /** Задать долю оффера и закрепить её; остальные доли пересчитываются */
  pinShare: StreamResult;
  /** Поставить задачу публикации: обработчик отправит в Keitaro активные офферы потока */
  publishStream: PublishStreamResult;
  /** Убрать оффер из черновика: он остаётся в потоке со статусом REMOVED и долей 0 */
  removeOffer: StreamResult;
  /** Повторить отклонённую публикацию новой задачей */
  retryTask: RetryTaskResult;
  /** Снять закрепление; оффер снова участвует в пересчёте */
  unpinShare: StreamResult;
};


export type MutationAddOfferArgs = {
  input: StreamOfferInput;
};


export type MutationBringBackOfferArgs = {
  input: StreamOfferInput;
};


export type MutationCancelDraftArgs = {
  expectedVersion?: InputMaybe<Scalars['Int']['input']>;
  streamId: Scalars['ID']['input'];
};


export type MutationCancelTaskArgs = {
  id: Scalars['ID']['input'];
};


export type MutationCreateCampaignArgs = {
  input: CreateCampaignInput;
};


export type MutationFetchStreamsArgs = {
  campaignKeitaroId: Scalars['Int']['input'];
};


export type MutationPinShareArgs = {
  input: PinShareInput;
};


export type MutationPublishStreamArgs = {
  input: PublishStreamInput;
};


export type MutationRemoveOfferArgs = {
  input: StreamOfferInput;
};


export type MutationRetryTaskArgs = {
  input: RetryTaskInput;
};


export type MutationUnpinShareArgs = {
  input: StreamOfferInput;
};

/** Оффер, заведённый в Keitaro */
export type Offer = {
  __typename?: 'Offer';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** Оффер уже получает трафик в этом потоке */
export type OfferAlreadyInStream = {
  __typename?: 'OfferAlreadyInStream';
  message: Scalars['String']['output'];
};

/** Оффера нет в Keitaro или в потоке — смотря что требовалось действию */
export type OfferNotFound = {
  __typename?: 'OfferNotFound';
  message: Scalars['String']['output'];
};

export type OfferState =
  | 'ACTIVE'
  | 'REMOVED';

/** Закрепить долю оффера */
export type PinShareInput = {
  /** Версия потока, которую видел пользователь; null — действовать по сохранённому сейчас */
  expectedVersion?: InputMaybe<Scalars['Int']['input']>;
  offerId: Scalars['Int']['input'];
  /** Доля от 1 до 100 */
  share: Scalars['Int']['input'];
  streamId: Scalars['ID']['input'];
};

/** Что опубликовать */
export type PublishStreamInput = {
  /** Версия потока, которую видел пользователь; null — действовать по сохранённому сейчас */
  expectedVersion?: InputMaybe<Scalars['Int']['input']>;
  streamId: Scalars['ID']['input'];
  /** Идентификатор новой задачи (UUID); повтор с ним же вернёт ту же задачу */
  taskId: Scalars['ID']['input'];
};

export type PublishStreamResult = EmptyStream | StreamBusy | StreamConflict | StreamNotFound | Task | TaskKeyReused;

/** Что было в Keitaro для оффера при последней загрузке или публикации */
export type PublishedOffer = {
  __typename?: 'PublishedOffer';
  pinned: Scalars['Boolean']['output'];
  share: Scalars['Int']['output'];
  state: OfferState;
};

export type Query = {
  __typename?: 'Query';
  /** Кампания по нашему идентификатору; null — такой нет */
  campaign?: Maybe<Campaign>;
  /** Кампании, известные сервису, сначала новые */
  campaigns: Array<Campaign>;
  /** Страны: поиск по названию или началу кода */
  countries: Array<Country>;
  /** Домены трекера, на которых можно разместить кампанию */
  domains: Array<Domain>;
  /** Группы кампаний */
  groups: Array<Group>;
  /** Активные офферы: поиск по фрагменту названия или началу ID */
  offers: Array<Offer>;
  /** Состояние событийной части */
  queueStatus: QueueStatus;
  /** Настройки сервиса, которые нужны интерфейсу */
  serviceInfo: ServiceInfo;
  /** Потоки кампании в том виде, в каком они сохранены у нас, по порядку */
  streams: Array<Stream>;
  /** Задача по идентификатору; null — такой нет */
  task?: Maybe<Task>;
  /** Задачи, сначала новые; без статусов — все */
  tasks: Array<Task>;
  /** Источники трафика */
  trafficSources: Array<TrafficSource>;
};


export type QueryCampaignArgs = {
  id: Scalars['ID']['input'];
};


export type QueryCountriesArgs = {
  search?: Scalars['String']['input'];
};


export type QueryOffersArgs = {
  limit?: Scalars['Int']['input'];
  search?: Scalars['String']['input'];
};


export type QueryStreamsArgs = {
  campaignId: Scalars['ID']['input'];
};


export type QueryTaskArgs = {
  id: Scalars['ID']['input'];
};


export type QueryTasksArgs = {
  first?: Scalars['Int']['input'];
  kind?: InputMaybe<TaskKind>;
  statuses?: InputMaybe<Array<TaskStatus>>;
};

/** Очередь шины сообщений */
export type QueueState = {
  __typename?: 'QueueState';
  /** Сколько обработчиков слушает очередь */
  consumers: Scalars['Int']['output'];
  name: Scalars['String']['output'];
  /** Сколько сообщений ждёт обработчика */
  ready: Scalars['Int']['output'];
};

/** Состояние событийной части: задачи, исходящие сообщения, очереди */
export type QueueStatus = {
  __typename?: 'QueueStatus';
  /** Когда записано самое старое из них, ISO 8601 */
  outboxOldest?: Maybe<Scalars['String']['output']>;
  /** Сообщения, которые ещё не ушли в шину */
  outboxWaiting: Scalars['Int']['output'];
  queues: Array<QueueState>;
  /** Только статусы, в которых есть задачи */
  tasks: Array<TaskCount>;
};

/** Что повторить */
export type RetryTaskInput = {
  /** Идентификатор новой задачи (UUID); повтор с ним же вернёт ту же задачу */
  newTaskId: Scalars['ID']['input'];
  /** Отклонённая задача */
  taskId: Scalars['ID']['input'];
};

export type RetryTaskResult = EmptyStream | StreamBusy | StreamNotFound | Task | TaskKeyReused | TaskNotFound | TaskNotRetryable;

/** Настройки сервиса, которые нужны интерфейсу */
export type ServiceInfo = {
  __typename?: 'ServiceInfo';
  /** Обязательное начало названия кампании */
  campaignNamePrefix: Scalars['String']['output'];
  /** Адрес трекера без пути: по нему строятся ссылки в админку Keitaro */
  trackerUrl: Scalars['String']['output'];
};

/** Закреплённые доли не дают разделить 100 % между активными офферами; черновик не изменён */
export type ShareOverflow = {
  __typename?: 'ShareOverflow';
  message: Scalars['String']['output'];
};

/** Поток кампании */
export type Stream = {
  __typename?: 'Stream';
  campaignId: Scalars['ID']['output'];
  /** Есть неопубликованные изменения */
  dirty: Scalars['Boolean']['output'];
  /** Наш идентификатор */
  id: Scalars['ID']['output'];
  /** Идентификатор потока в Keitaro */
  keitaroId: Scalars['Int']['output'];
  /** Схема потока в Keitaro: landings — офферы, redirect — перенаправление */
  kind: Scalars['String']['output'];
  name: Scalars['String']['output'];
  /** Офферы в порядке добавления; у потока-перенаправления список пуст */
  offers: Array<StreamOffer>;
  /** Порядковый номер в кампании */
  position: Scalars['Int']['output'];
  /** Задача публикации, которая сейчас выполняется; пока она есть, поток занят */
  publishingTaskId?: Maybe<Scalars['ID']['output']>;
  /** Номер записи потока: растёт при каждом изменении, возвращается обратно с действием */
  version: Scalars['Int']['output'];
};

/** Поток публикуется: до завершения задачи он не правится и не перезагружается */
export type StreamBusy = {
  __typename?: 'StreamBusy';
  message: Scalars['String']['output'];
};

/** Поток изменён после того, как его показали пользователю; действие не применено */
export type StreamConflict = {
  __typename?: 'StreamConflict';
  message: Scalars['String']['output'];
  /** Поток, каким он сохранён сейчас */
  stream: Stream;
};

/** У нас нет такого потока */
export type StreamNotFound = {
  __typename?: 'StreamNotFound';
  message: Scalars['String']['output'];
};

/** Оффер в потоке: черновик и опубликованный снимок */
export type StreamOffer = {
  __typename?: 'StreamOffer';
  /** Публикация изменит этот оффер в Keitaro */
  changed: Scalars['Boolean']['output'];
  name: Scalars['String']['output'];
  offerId: Scalars['Int']['output'];
  /** Доля закреплена и не меняется при пересчёте */
  pinned: Scalars['Boolean']['output'];
  /** Опубликованный снимок; null — оффер ещё не публиковался */
  published?: Maybe<PublishedOffer>;
  /** Доля в процентах; у убранного оффера 0 */
  share: Scalars['Int']['output'];
  state: OfferState;
};

/** Оффер в потоке, над которым выполняется действие */
export type StreamOfferInput = {
  /** Версия потока, которую видел пользователь; null — действовать по сохранённому сейчас */
  expectedVersion?: InputMaybe<Scalars['Int']['input']>;
  offerId: Scalars['Int']['input'];
  streamId: Scalars['ID']['input'];
};

export type StreamResult = KeitaroFailure | OfferAlreadyInStream | OfferNotFound | ShareOverflow | Stream | StreamBusy | StreamConflict | StreamNotFound | ValidationFailed;

/** Потоки загружены из Keitaro и сохранены */
export type StreamsFetched = {
  __typename?: 'StreamsFetched';
  campaign: Campaign;
  streams: Array<Stream>;
};

/** Изменение в Keitaro, которое выполняется отдельно от запроса */
export type Task = {
  __typename?: 'Task';
  /** Сколько раз обработчик брался за задачу */
  attempts: Scalars['Int']['output'];
  campaignId?: Maybe<Scalars['ID']['output']>;
  /** Время в ISO 8601 */
  createdAt: Scalars['String']['output'];
  finishedAt?: Maybe<Scalars['String']['output']>;
  /** Идентификатор выдаёт клиент; он же ключ идемпотентности */
  id: Scalars['ID']['output'];
  kind: TaskKind;
  /** Причина отказа; есть только у задачи со статусом REJECTED */
  refusal?: Maybe<TaskRefusal>;
  /** Отклонённая задача, которую повторяет эта */
  retryOf?: Maybe<Scalars['ID']['output']>;
  startedAt?: Maybe<Scalars['String']['output']>;
  status: TaskStatus;
  steps: Array<TaskStep>;
  streamId?: Maybe<Scalars['ID']['output']>;
};

/** Сколько задач в одном статусе */
export type TaskCount = {
  __typename?: 'TaskCount';
  count: Scalars['Int']['output'];
  status: TaskStatus;
};

/** Этот идентификатор задачи уже использован для другого запроса */
export type TaskKeyReused = {
  __typename?: 'TaskKeyReused';
  message: Scalars['String']['output'];
};

export type TaskKind =
  | 'CREATE_CAMPAIGN'
  | 'PUBLISH_STREAM';

/** Отменить можно только задачу, за которую обработчик ещё не взялся */
export type TaskNotCancellable = {
  __typename?: 'TaskNotCancellable';
  message: Scalars['String']['output'];
};

export type TaskNotFound = {
  __typename?: 'TaskNotFound';
  message: Scalars['String']['output'];
};

/** Повторить можно только отклонённую публикацию */
export type TaskNotRetryable = {
  __typename?: 'TaskNotRetryable';
  message: Scalars['String']['output'];
};

/** Почему задача завершилась отказом */
export type TaskRefusal = {
  __typename?: 'TaskRefusal';
  /** Домен, который успел создаться до отказа и остался в трекере */
  createdDomain?: Maybe<Domain>;
  message: Scalars['String']['output'];
};

export type TaskStatus =
  | 'CANCELLED'
  | 'PENDING'
  | 'REJECTED'
  | 'RUNNING'
  | 'SUCCEEDED';

/** Что задача сделала, по порядку */
export type TaskStep = {
  __typename?: 'TaskStep';
  /** Время в ISO 8601 */
  at: Scalars['String']['output'];
  name: Scalars['String']['output'];
  note: Scalars['String']['output'];
};

/** Источник трафика */
export type TrafficSource = {
  __typename?: 'TrafficSource';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** Ввод не прошёл проверку; в Keitaro ничего не изменено */
export type ValidationFailed = {
  __typename?: 'ValidationFailed';
  fields: Array<FieldError>;
  message: Scalars['String']['output'];
};
