import sqlite3
import networkx as nx
import json
import logging
import os
from hermes.memory.chroma_store import HermesMemory

logger = logging.getLogger("hermes.memory.graph")

class GraphStore:
    """
    SQLite-backed Knowledge Graph using NetworkX for traversal.
    Integrates ChromaDB for semantic entity resolution.
    """
    def __init__(self, db_path="graph_memory.db"):
        self.db_path = db_path
        self._init_db()
        try:
            # Initialize ChromaDB vector space for entities
            self.vector_store = HermesMemory(collection_name="hermes_entities")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB entity store: {e}")
            self.vector_store = None

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # We store the directed edges (triples): source -> predicate -> target
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT,
                    predicate TEXT,
                    target TEXT,
                    metadata TEXT,
                    UNIQUE(source, predicate, target)
                )
            ''')
            conn.commit()

    def add_triple(self, source: str, predicate: str, target: str, metadata: dict = None):
        """Add a single relationship to the graph and embed its entities."""
        meta_str = json.dumps(metadata) if metadata else "{}"
        src_norm = source.lower().strip()
        tgt_norm = target.lower().strip()
        pred_norm = predicate.lower().strip()
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR IGNORE INTO edges (source, predicate, target, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (src_norm, pred_norm, tgt_norm, meta_str))
                conn.commit()
                logger.info(f"Added Graph Triple: [{src_norm}] -> ({pred_norm}) -> [{tgt_norm}]")
        except Exception as e:
            logger.error(f"Failed to add triple to SQLite: {e}")
            
        # Store in ChromaDB vector space for semantic similarity searches
        if self.vector_store:
            try:
                self.vector_store.store(src_norm, {"type": "entity", "name": src_norm})
                self.vector_store.store(tgt_norm, {"type": "entity", "name": tgt_norm})
                logger.debug(f"Stored entities '{src_norm}' and '{tgt_norm}' in ChromaDB.")
            except Exception as e:
                logger.error(f"Failed to store entities in ChromaDB: {e}")

    def get_networkx_graph(self) -> nx.DiGraph:
        """Loads the entire SQLite edge list into a NetworkX directed graph for fast traversal."""
        G = nx.DiGraph()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT source, predicate, target FROM edges")
            for src, pred, tgt in cursor.fetchall():
                G.add_edge(src, tgt, predicate=pred)
        return G

    def query_neighborhood(self, entity: str, depth: int = 2) -> list:
        """
        Finds all relationships connected to `entity` up to `depth` degrees away.
        Resolves semantic variations using the ChromaDB entity vector space.
        Returns a list of human-readable relationship strings.
        """
        G = self.get_networkx_graph()
        entity_norm = entity.lower().strip()
        
        # 1. Resolve entity names semantically
        resolved_entities = []
        if self.vector_store:
            try:
                # Retrieve top 3 semantically close entities from ChromaDB
                matches = self.vector_store.recall(entity_norm, top_k=3)
                resolved_entities = list(set([m.lower().strip() for m in matches if m]))
            except Exception as e:
                logger.error(f"Semantic entity recall failed: {e}")
                
        # Ensure the queried entity itself is always checked
        if entity_norm not in resolved_entities:
            resolved_entities.append(entity_norm)
            
        logger.info(f"Resolved query '{entity_norm}' to semantic entities: {resolved_entities}")
        
        results = []
        visited_edges = set()
        
        # 2. Traverse egocentric subgraphs for all resolved entities
        for ent in resolved_entities:
            if ent not in G:
                continue
                
            subgraph = nx.ego_graph(G, ent, radius=depth)
            
            for src, tgt, data in subgraph.edges(data=True):
                pred = data.get("predicate", "related_to")
                edge_key = (src, pred, tgt)
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                    results.append(f"[{src}] --{pred}--> [{tgt}]")
                    
        return results
