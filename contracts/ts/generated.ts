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
  trafficSourceId: Scalars['Int']['input'];
};

export type CreateCampaignResult = Campaign | KeitaroFailure | ValidationFailed;

/** Домен трекера, на котором размещается кампания */
export type Domain = {
  __typename?: 'Domain';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

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
  /** Создать кампанию: поток 1 уводит страну на Google, поток 2 ведёт на оффер */
  createCampaign: CreateCampaignResult;
};


export type MutationCreateCampaignArgs = {
  input: CreateCampaignInput;
};

/** Оффер, заведённый в Keitaro */
export type Offer = {
  __typename?: 'Offer';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

export type Query = {
  __typename?: 'Query';
  /** Страны: поиск по названию или началу кода */
  countries: Array<Country>;
  /** Домены трекера, на которых можно разместить кампанию */
  domains: Array<Domain>;
  /** Группы кампаний */
  groups: Array<Group>;
  /** Активные офферы: поиск по фрагменту названия или началу ID */
  offers: Array<Offer>;
  /** Источники трафика */
  trafficSources: Array<TrafficSource>;
};


export type QueryCountriesArgs = {
  search?: Scalars['String']['input'];
};


export type QueryOffersArgs = {
  limit?: Scalars['Int']['input'];
  search?: Scalars['String']['input'];
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
