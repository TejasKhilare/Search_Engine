import DocumentList from "./DocumentList"
import UploadButton from "./UploadButton"

export default function Sidebar() {
  return (
    <div className="w-64 bg-gray-100 p-4 h-screen flex flex-col">
      <h2 className="text-lg font-semibold mb-4">Documents</h2>

      <UploadButton />

      <div className="mt-4 flex-1 overflow-y-auto">
        <DocumentList />
      </div>
    </div>
  )
}