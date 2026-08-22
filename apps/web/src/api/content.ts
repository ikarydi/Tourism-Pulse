import { request } from './client'
import {
  newsArticleToContentItem,
  videoItemToContentItem,
  type ContentItem,
  type NewsArticle,
  type VideoItem,
} from '../types/content'

// The extensibility point (see types/content.ts): fetches every content
// source for a place and normalizes them into one ContentItem[], sorted
// newest-first. Adding a new source later (a future social-media table
// following the same NewsArticle/VideoItem pattern) means adding one
// more Promise.all branch and normalizer function here - the UI
// (components/ContentFeed.tsx) never changes.
export async function getPlaceContent(placeId: number): Promise<ContentItem[]> {
  const [articles, videos] = await Promise.all([
    request<NewsArticle[]>(`/places/${placeId}/news`),
    request<VideoItem[]>(`/places/${placeId}/videos`),
  ])

  const items = [
    ...articles.map(newsArticleToContentItem),
    ...videos.map(videoItemToContentItem),
  ]

  return items.sort((a, b) => {
    const aTime = a.published_at ? new Date(a.published_at).getTime() : 0
    const bTime = b.published_at ? new Date(b.published_at).getTime() : 0
    return bTime - aTime
  })
}
