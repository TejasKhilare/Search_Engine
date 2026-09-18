import { create } from "zustand"

export const BUSY_STATUSES = new Set(["pending", "processing"])

const initialState = {
  documents: [],
  total: 0,
  loaded: false,
  // When set, search and AI answers are limited to this document
  selectedDoc: null,
}

export const useDocumentStore = create((set) => ({
  ...initialState,

  setPage: ({ items, total }, { append = false } = {}) =>
    set((state) => ({
      documents: append ? [...state.documents, ...items.filter((d) => !state.documents.some((x) => x.id === d.id))] : items,
      total,
      loaded: true,
    })),

  /** Insert a new document at the top, or replace an existing one in place. */
  upsertDocument: (doc) =>
    set((state) => {
      const exists = state.documents.some((d) => d.id === doc.id)
      return {
        documents: exists
          ? state.documents.map((d) => (d.id === doc.id ? doc : d))
          : [doc, ...state.documents],
        total: exists ? state.total : state.total + 1,
        selectedDoc: state.selectedDoc?.id === doc.id ? doc : state.selectedDoc,
      }
    }),

  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
      total: Math.max(0, state.total - 1),
      selectedDoc: state.selectedDoc?.id === id ? null : state.selectedDoc,
    })),

  /** Clicking the selected document again clears the selection. */
  toggleSelectedDoc: (doc) =>
    set((state) => ({ selectedDoc: state.selectedDoc?.id === doc?.id ? null : doc })),

  clearSelectedDoc: () => set({ selectedDoc: null }),

  reset: () => set(initialState),
}))
