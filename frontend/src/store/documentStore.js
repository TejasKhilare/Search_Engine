import { create } from "zustand"

export const useDocumentStore = create((set) => ({
  documents: [],
  selectedDoc: null,
  loading: false,

  setDocuments: (docs) => set({ documents: docs }),
  setSelectedDoc: (doc) => set({ selectedDoc: doc }),
  setLoading: (val) => set({ loading: val }),

  removeDocument: (docId) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.doc_id !== docId),
    })),

  updateDocumentStatus: (docId, status) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.doc_id === docId ? { ...d, status } : d
      ),
    })),
}))