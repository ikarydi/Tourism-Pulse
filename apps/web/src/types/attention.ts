// Mirrors schemas/attention.py.
export type LanguageShare = {
  language: string
  name: string
  views_12m: number
  share: number
  previous_share: number | null
  growth: number | null
}

export type TopicShare = {
  topic: string
  label: string
  articles_12m: number
  share: number
  previous_share: number | null
  europe_share: number | null
  lift: number | null
}

export type WikipediaInsight = {
  latest_month: string
  latest_views: number
  latest_vs_last_year: number | null
  benchmark_vs_last_year: number | null
  relative_to_benchmark: number | null
  views_12m: number | null
  views_12m_vs_previous: number | null
  languages: LanguageShare[]
  lead: { months: number; correlation: number; observations: number; nights_place: string } | null
  series: { period: string; value: number }[]
}

export type NewsInsight = {
  latest_month: string
  attention_share: number | null
  attention_vs_last_year: number | null
  tourism_share: number | null
  tourism_articles_12m: number
  tone_3m: number | null
  tone_3m_last_year: number | null
  topics: TopicShare[]
  series: { period: string; attention_share: number; tone: number | null }[]
}

export type Attention = {
  place_id: number
  place_name: string
  wikipedia: WikipediaInsight | null
  news: NewsInsight | null
  highlights: string[]
}

export type AttentionSummary = {
  place_id: number
  name: string
  place_type: string
  country_code: string | null
  wiki_month: string | null
  wiki_vs_last_year: number | null
  wiki_relative: number | null
  language_gainer: string | null
  language_gain: number | null
  news_month: string | null
  news_vs_last_year: number | null
  tone_3m: number | null
  tone_change: number | null
  tourism_articles_12m: number
  top_topic: string | null
  top_topic_share: number | null
  top_topic_lift: number | null
  highlights: string[]
}
