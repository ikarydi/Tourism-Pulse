// Raw API shapes - one per source, matching schemas/news_article.py /
// video_item.py exactly.
export type NewsArticle = {
  id: number
  place_id: number
  source: string
  url: string
  title: string
  domain: string | null
  published_at: string | null
  tone: number | null
  categories: string[]
  retrieved_at: string
}

export type VideoItem = {
  id: number
  place_id: number
  source: string
  video_id: string
  title: string
  channel: string | null
  published_at: string | null
  categories: string[]
  retrieved_at: string
}

// The extensibility point: every content source (news, video, and
// whatever social-media source lands next) normalizes into this one
// shape at the API-client layer (see api/content.ts) - the UI never
// needs a second feed component, only a new case in that normalizer.
export type ContentItem = {
  id: string
  kind: 'news' | 'video'
  source: string
  title: string
  url: string
  byline: string | null // domain for news, channel for video
  published_at: string | null
  categories: string[]
  tone: number | null // news only
}

export function newsArticleToContentItem(article: NewsArticle): ContentItem {
  return {
    id: `news-${article.id}`,
    kind: 'news',
    source: article.source,
    title: article.title,
    url: article.url,
    byline: article.domain,
    published_at: article.published_at,
    categories: article.categories,
    tone: article.tone,
  }
}

export function videoItemToContentItem(video: VideoItem): ContentItem {
  return {
    id: `video-${video.id}`,
    kind: 'video',
    source: video.source,
    title: video.title,
    url: `https://www.youtube.com/watch?v=${video.video_id}`,
    byline: video.channel,
    published_at: video.published_at,
    categories: video.categories,
    tone: null,
  }
}
