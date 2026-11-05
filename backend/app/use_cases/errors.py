class EmbeddingModelMismatchError(RuntimeError):
    """Raised when a document's vectors were produced by a different embedding model."""

    def __init__(self, document_name: str, stored_model: str, current_model: str) -> None:
        super().__init__(
            f"Document '{document_name}' was processed with embedding model "
            f"'{stored_model}', but the current model is '{current_model}'. "
            "Upload the PDF again to process it with the current model."
        )
