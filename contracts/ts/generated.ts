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

/** Страна ISO 3166-1 */
export type Country = {
  __typename?: 'Country';
  /** Код alpha-2 в верхнем регистре */
  code: Scalars['String']['output'];
  name: Scalars['String']['output'];
};

/** Домен трекера, на котором размещается кампания */
export type Domain = {
  __typename?: 'Domain';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
};

/** Группа кампаний */
export type Group = {
  __typename?: 'Group';
  id: Scalars['Int']['output'];
  name: Scalars['String']['output'];
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
