"""
Pydantic schemas for Weaviate API request/response payloads.

Models the subset of the Weaviate REST API used in Phase 1.
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class WeaviatePropertySchema(BaseModel):
    """A single property definition in a Weaviate class schema."""
    name: str
    dataType: List[str]
    description: Optional[str] = None


class WeaviateCreateClassRequest(BaseModel):
    """
    Payload for POST /v1/schema.

    Phase 1 creates a minimal class with no custom properties.
    Properties will be added in Phase 2 when document ingestion is built.
    """
    # ``class`` is a Python reserved word; alias used in serialisation
    class_name: str
    description: Optional[str] = None
    vectorizer: str = "none"
    properties: List[WeaviatePropertySchema] = []

    def to_weaviate_dict(self) -> Dict[str, Any]:
        """Serialise to the exact dict Weaviate expects."""
        d: Dict[str, Any] = {
            "class": self.class_name,
            "vectorizer": self.vectorizer,
        }
        if self.description:
            d["description"] = self.description
        if self.properties:
            d["properties"] = [p.model_dump() for p in self.properties]
        return d
