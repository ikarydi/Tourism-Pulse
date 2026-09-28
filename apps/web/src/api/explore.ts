import { request } from './client'
import type { AskAnswer, Catalog, QueryResult, QuerySpec, SavedView, ViewSpec } from '../types/explore'

const json = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
})

export const getCatalog = () => request<Catalog>('/explore/catalog')

export const runQuery = (spec: QuerySpec) => request<QueryResult>('/explore/query', json(spec))

export const askQuestion = (question: string) => request<AskAnswer>('/explore/ask', json({ question }))

export const listViews = () => request<SavedView[]>('/explore/views')

export const createView = (title: string, spec: ViewSpec, description?: string) =>
  request<SavedView>('/explore/views', json({ title, spec, description: description ?? null }))

export const updateView = (id: number, changes: Partial<Pick<SavedView, 'title' | 'pinned' | 'position'>> & { spec?: ViewSpec }) =>
  request<SavedView>(`/explore/views/${id}`, { ...json(changes), method: 'PUT' })

export const deleteView = (id: number) => request<void>(`/explore/views/${id}`, { method: 'DELETE' })
