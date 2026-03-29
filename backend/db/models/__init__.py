"""Model registry.

Importing any single model module triggers this package ``__init__``, which in
turn imports every model. That guarantees SQLAlchemy's mapper can resolve
cross-table foreign keys (e.g. ``Document.user_id -> users.id``) no matter which
entry point — the FastAPI app, the Celery worker, or a standalone script like
``scripts.arxiv_ingest`` — loads the models first.
"""

from backend.db.models.user import User
from backend.db.models.document import Document
from backend.db.models.chunk import Chunk
from backend.db.models.conversation import ConversationHistory

__all__ = ["User", "Document", "Chunk", "ConversationHistory"]
