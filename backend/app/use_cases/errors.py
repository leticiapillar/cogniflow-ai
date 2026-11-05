class EmbeddingModelMismatchError(RuntimeError):
    """Raised when a document's vectors were produced by a different embedding model."""

    def __init__(self, document_name: str, stored_model: str, current_model: str) -> None:
        super().__init__(
            f"Document '{document_name}' was processed with embedding model "
            f"'{stored_model}', but the current model is '{current_model}'. "
            "Upload the PDF again to process it with the current model."
        )


class DocumentNotFoundError(LookupError):
    """Raised when the requested document does not exist."""


class MindMapNotFoundError(LookupError):
    """Raised when a document has no mind map yet (e.g. ingested before map-reduce existed)."""


class GenerationInProgressError(RuntimeError):
    """Raised when a mind map generation is already pending or running for the document."""


class SectionNotRetryableError(RuntimeError):
    """Raised when a section cannot be retried (it did not fail or does not exist)."""
