import api from "../../shared/utils/axios"

/**
 * Hybrid search. Returns { query, results: [{ document_id, filename, page_number,
 * snippet: { text, highlights }, score, match_types, ... }], took_ms }.
 */
export const searchDocuments = async (query, { documentId, signal } = {}) => {
  const res = await api.get("/search", {
    params: { q: query, document_id: documentId || undefined },
    signal,
  })
  return res.data
}
