from pydantic import BaseModel


class DocumentArtifact(BaseModel):
    document_id: str
    title: str
    backend: str  # "google_docs" or "local"
    created_at: str
    updated_at: str
    char_count: int
    url: str | None = None
    google_doc_id: str | None = None
    file_path: str | None = None
