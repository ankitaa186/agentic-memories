"""ChromaDB mock fixtures for testing."""

from typing import Any, Dict, List, Optional


class MockV2Collection:
    """Mock V2Collection for testing."""

    def __init__(self, client, name: str, collection_id: str):
        self.client = client
        self.name = name
        self.collection_id = collection_id
        self._data: Dict[str, Any] = {}
        self._ids: List[str] = []
        self._embeddings: List[List[float]] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._documents: List[str] = []

    def add(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock add method."""
        self._ids.extend(ids)
        if embeddings:
            self._embeddings.extend(embeddings)
        if metadatas:
            self._metadatas.extend(metadatas)
        if documents:
            self._documents.extend(documents)

    def upsert(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock upsert method."""
        # Remove existing IDs first
        for id_to_remove in ids:
            if id_to_remove in self._ids:
                idx = self._ids.index(id_to_remove)
                self._ids.pop(idx)
                if self._embeddings and idx < len(self._embeddings):
                    self._embeddings.pop(idx)
                if self._metadatas and idx < len(self._metadatas):
                    self._metadatas.pop(idx)
                if self._documents and idx < len(self._documents):
                    self._documents.pop(idx)

        # Add new data
        self.add(ids, embeddings, metadatas, documents)

    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mock query method."""
        # Simple mock that returns some results
        mock_results = {
            "ids": [["mem_1", "mem_2"]],
            "embeddings": [[[0.1] * 16, [0.2] * 16]],
            "metadatas": [
                [
                    {"user_id": "test_user", "layer": "semantic"},
                    {"user_id": "test_user", "layer": "short-term"},
                ]
            ],
            "documents": [["User loves sci-fi books.", "User is planning a vacation."]],
            "distances": [[0.1, 0.2]],
        }
        return mock_results

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mock get method."""
        return {
            "ids": self._ids,
            "embeddings": self._embeddings,
            "metadatas": self._metadatas,
            "documents": self._documents,
        }

    def update(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock update method."""
        for i, id_to_update in enumerate(ids):
            if id_to_update in self._ids:
                idx = self._ids.index(id_to_update)
                if embeddings and i < len(embeddings):
                    self._embeddings[idx] = embeddings[i]
                if metadatas and i < len(metadatas):
                    self._metadatas[idx] = metadatas[i]
                if documents and i < len(documents):
                    self._documents[idx] = documents[i]

    def delete(self, ids: List[str]) -> None:
        """Mock delete method."""
        for id_to_delete in ids:
            if id_to_delete in self._ids:
                idx = self._ids.index(id_to_delete)
                self._ids.pop(idx)
                if self._embeddings and idx < len(self._embeddings):
                    self._embeddings.pop(idx)
                if self._metadatas and idx < len(self._metadatas):
                    self._metadatas.pop(idx)
                if self._documents and idx < len(self._documents):
                    self._documents.pop(idx)


class MockChromaCollection:
    """Mock ChromaDB collection for testing."""

    def __init__(self, name: str = "memories_3072"):
        self.name = name
        self._data: Dict[str, Any] = {}
        self._ids: List[str] = []
        self._embeddings: List[List[float]] = []
        self._metadatas: List[Dict[str, Any]] = []
        self._documents: List[str] = []

    def add(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock add method."""
        self._ids.extend(ids)
        if embeddings:
            self._embeddings.extend(embeddings)
        if metadatas:
            self._metadatas.extend(metadatas)
        if documents:
            self._documents.extend(documents)

    def upsert(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock upsert method."""
        # Remove existing IDs first
        for id_to_remove in ids:
            if id_to_remove in self._ids:
                idx = self._ids.index(id_to_remove)
                self._ids.pop(idx)
                if self._embeddings and idx < len(self._embeddings):
                    self._embeddings.pop(idx)
                if self._metadatas and idx < len(self._metadatas):
                    self._metadatas.pop(idx)
                if self._documents and idx < len(self._documents):
                    self._documents.pop(idx)

        # Add new data
        self.add(ids, embeddings, metadatas, documents)

    def query(
        self,
        query_embeddings: Optional[List[List[float]]] = None,
        query_texts: Optional[List[str]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mock query method."""
        # Simple mock that returns some results
        mock_results = {
            "ids": [["mem_1", "mem_2"]],
            "embeddings": [[[0.1] * 16, [0.2] * 16]],
            "metadatas": [
                [
                    {"user_id": "test_user", "layer": "semantic"},
                    {"user_id": "test_user", "layer": "short-term"},
                ]
            ],
            "documents": [["User loves sci-fi books.", "User is planning a vacation."]],
            "distances": [[0.1, 0.2]],
        }
        return mock_results

    def get(
        self,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
        include: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Mock get method."""
        return {
            "ids": self._ids,
            "embeddings": self._embeddings,
            "metadatas": self._metadatas,
            "documents": self._documents,
        }

    def update(
        self,
        ids: List[str],
        embeddings: Optional[List[List[float]]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        documents: Optional[List[str]] = None,
    ) -> None:
        """Mock update method."""
        for i, id_to_update in enumerate(ids):
            if id_to_update in self._ids:
                idx = self._ids.index(id_to_update)
                if embeddings and i < len(embeddings):
                    self._embeddings[idx] = embeddings[i]
                if metadatas and i < len(metadatas):
                    self._metadatas[idx] = metadatas[i]
                if documents and i < len(documents):
                    self._documents[idx] = documents[i]

    def delete(self, ids: List[str]) -> None:
        """Mock delete method."""
        for id_to_delete in ids:
            if id_to_delete in self._ids:
                idx = self._ids.index(id_to_delete)
                self._ids.pop(idx)
                if self._embeddings and idx < len(self._embeddings):
                    self._embeddings.pop(idx)
                if self._metadatas and idx < len(self._metadatas):
                    self._metadatas.pop(idx)
                if self._documents and idx < len(self._documents):
                    self._documents.pop(idx)


class MockV2ChromaClient:
    """Mock V2ChromaClient for testing."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8000,
        tenant: str = "agentic-memories",
        database: str = "memories",
    ):
        self.host = host
        self.port = port
        self.tenant = tenant
        self.database = database
        self._collections: Dict[str, MockV2Collection] = {}

    def heartbeat(self) -> Dict[str, Any]:
        """Mock heartbeat method."""
        return {"status": "ok"}

    def _make_request(
        self, method: str, endpoint: str, json_data: Optional[Dict] = None
    ) -> Any:
        """Mock _make_request method to avoid HTTP calls."""
        if endpoint == "/heartbeat":
            return {"status": "ok"}
        elif (
            endpoint == f"/tenants/{self.tenant}/databases/{self.database}/collections"
        ):
            if method.upper() == "GET":
                return [
                    {"name": name, "id": col.collection_id}
                    for name, col in self._collections.items()
                ]
            elif method.upper() == "POST" and json_data:
                name = json_data.get("name")
                if name:
                    collection_id = f"col_{name}_{len(self._collections)}"
                    self._collections[name] = MockV2Collection(
                        self, name, collection_id
                    )
                    return {"id": collection_id}
        return {}

    def get_or_create_collection(self, name: str) -> MockV2Collection:
        """Mock get_or_create_collection method."""
        if name not in self._collections:
            collection_id = f"col_{name}_{len(self._collections)}"
            self._collections[name] = MockV2Collection(self, name, collection_id)
        return self._collections[name]

    def get_collection(self, name: str) -> MockV2Collection:
        """Mock get_collection method."""
        if name not in self._collections:
            raise ValueError(f"Collection {name} not found")
        return self._collections[name]

    def list_collections(self) -> List[Dict[str, Any]]:
        """Mock list_collections method."""
        return [
            {"name": name, "id": col.collection_id}
            for name, col in self._collections.items()
        ]


class MockChromaClient:
    """Mock ChromaDB client for testing."""

    def __init__(self):
        self._collections: Dict[str, MockChromaCollection] = {}

    def get_or_create_collection(
        self, name: str, metadata: Optional[Dict[str, Any]] = None
    ) -> MockChromaCollection:
        """Mock get_or_create_collection method."""
        if name not in self._collections:
            self._collections[name] = MockChromaCollection(name)
        return self._collections[name]

    def get_collection(self, name: str) -> MockChromaCollection:
        """Mock get_collection method."""
        if name not in self._collections:
            raise ValueError(f"Collection {name} not found")
        return self._collections[name]

    def list_collections(self) -> List[Dict[str, Any]]:
        """Mock list_collections method."""
        return [{"name": name} for name in self._collections.keys()]


def create_mock_v2_chroma_client() -> MockV2ChromaClient:
    """Create a mock V2ChromaClient."""
    return MockV2ChromaClient()


def create_mock_chroma_client() -> MockChromaClient:
    """Create a mock ChromaDB client."""
    return MockChromaClient()


def create_mock_collection(name: str = "memories_3072") -> MockChromaCollection:
    """Create a mock ChromaDB collection."""
    return MockChromaCollection(name)
