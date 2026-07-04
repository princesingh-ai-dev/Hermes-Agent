# hermes/memory/chroma_store.py
import chromadb
from sentence_transformers import SentenceTransformer
import hermes.core.config as config

class HermesMemory:
    def __init__(self, db_path: str = None, collection_name: str = "hermes"):
        if db_path is None:
            db_path = config.HERMES_MEMORY_PATH
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(collection_name)
        # Free local embeddings - no API key, runs on CPU
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")
        
    def store(self, text: str, metadata: dict = None) -> None:
        if metadata is None:
            metadata = {}
        embedding = self.embedder.encode(text).tolist()
        kwargs = {
            "documents": [text],
            "embeddings": [embedding],
            "ids": [f"mem_{hash(text)}"]
        }
        if metadata:
            kwargs["metadatas"] = [metadata]
        self.collection.add(**kwargs)
        
    def recall(self, query: str, top_k: int = 5) -> list:
        embedding = self.embedder.encode(query).tolist()
        results = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        if results["documents"]:
            return results["documents"][0]
        return []
