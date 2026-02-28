"""
Vector Search Engine (Level 3)
Semantic Search using Sentence Transformers

Features:
- Semantic similarity search (not just keyword matching)
- Multi-lingual support (Thai + English)
- Efficient vector storage and retrieval
- Hybrid search (vector + keyword)
"""

import json
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Optional


class VectorSearchEngine:
    """Semantic search using sentence embeddings"""

    def __init__(self, model_name='paraphrase-multilingual-mpnet-base-v2', use_gpu=False):
        """
        Args:
            model_name: SentenceTransformer model to use
            use_gpu: Use GPU for encoding (faster but requires CUDA)
        """
        self.model_name = model_name
        self.use_gpu = use_gpu

        # Lazy loading - only load when needed
        self.model = None
        self.inspection_index = None
        self.inspection_metadata = []
        self.document_index = None
        self.document_metadata = []

        print(f"✓ Vector Search Engine initialized")
        print(f"  → Model: {model_name}")
        print(f"  → GPU: {'enabled' if use_gpu else 'disabled'}")
        print(f"  → Note: Model will be loaded on first use")

    def _load_model(self):
        """Lazy load the sentence transformer model"""
        if self.model is not None:
            return

        try:
            from sentence_transformers import SentenceTransformer
            import torch

            device = 'cuda' if self.use_gpu and torch.cuda.is_available() else 'cpu'
            print(f"📦 Loading SentenceTransformer model ({self.model_name})...")
            self.model = SentenceTransformer(self.model_name, device=device)
            print(f"✅ Model loaded on {device}")
        except ImportError:
            print("❌ sentence-transformers not installed")
            print("   Install: pip install sentence-transformers")
            raise
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            raise

    def index_inspections(self, inspections: List[Dict[str, Any]]):
        """
        Create vector index from inspection records

        Args:
            inspections: List of inspection dicts with keys:
                        id, timestamp, device_id, result, station, etc.
        """
        if not inspections:
            print("⚠️ No inspections to index")
            return

        self._load_model()

        print(f"📊 Indexing {len(inspections)} inspections...")

        # Create text descriptions for each inspection
        texts = []
        for insp in inspections:
            # Create searchable text
            text = f"{insp.get('device_id', '')} {insp.get('result', '')} at {insp.get('station', '')} {insp.get('timestamp', '')}"
            texts.append(text)

        # Generate embeddings
        print("🔄 Generating embeddings...")
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        # Store in index
        self.inspection_index = embeddings
        self.inspection_metadata = inspections

        print(f"✅ Indexed {len(inspections)} inspections")
        print(f"   Vector dimension: {embeddings.shape[1]}")

    def index_documents(self, documents: List[Dict[str, Any]]):
        """
        Create vector index from documents

        Args:
            documents: List of document dicts with keys:
                      filename, content, metadata, etc.
        """
        if not documents:
            print("⚠️ No documents to index")
            return

        self._load_model()

        print(f"📚 Indexing {len(documents)} documents...")

        # Create text for each document
        texts = []
        for doc in documents:
            # Use content or combine title + content
            text = doc.get('content', '')
            if 'filename' in doc:
                text = doc['filename'] + " " + text
            texts.append(text[:1000])  # Limit length

        # Generate embeddings
        print("🔄 Generating embeddings...")
        embeddings = self.model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

        # Store in index
        self.document_index = embeddings
        self.document_metadata = documents

        print(f"✅ Indexed {len(documents)} documents")
        print(f"   Vector dimension: {embeddings.shape[1]}")

    def search_inspections(self, query: str, top_k: int = 10, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Semantic search for inspections

        Args:
            query: Search query (natural language)
            top_k: Number of results to return
            threshold: Minimum similarity score (0-1)

        Returns:
            List of results with scores
        """
        if self.inspection_index is None:
            return []

        self._load_model()

        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # Calculate cosine similarity
        similarities = self._cosine_similarity(query_embedding, self.inspection_index)

        # Get top k results
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= threshold:
                result = self.inspection_metadata[idx].copy()
                result['_score'] = score
                results.append(result)

        return results

    def search_documents(self, query: str, top_k: int = 5, threshold: float = 0.3) -> List[Dict[str, Any]]:
        """
        Semantic search for documents

        Args:
            query: Search query
            top_k: Number of results
            threshold: Minimum similarity

        Returns:
            List of document results with scores
        """
        if self.document_index is None:
            return []

        self._load_model()

        # Encode query
        query_embedding = self.model.encode([query], convert_to_numpy=True)[0]

        # Calculate similarity
        similarities = self._cosine_similarity(query_embedding, self.document_index)

        # Get top k
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            score = float(similarities[idx])
            if score >= threshold:
                result = self.document_metadata[idx].copy()
                result['_score'] = score
                results.append(result)

        return results

    def hybrid_search_inspections(self, query: str, keyword_results: List[Dict], top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Hybrid search: Combine vector search + keyword search

        Args:
            query: Search query
            keyword_results: Results from keyword search
            top_k: Final number of results

        Returns:
            Combined and re-ranked results
        """
        # Get vector search results
        vector_results = self.search_inspections(query, top_k=top_k * 2)

        # Combine results using RRF (Reciprocal Rank Fusion)
        combined_scores = {}

        # Add vector results
        for rank, result in enumerate(vector_results):
            doc_id = result.get('id', str(rank))
            score = result.get('_score', 0)
            combined_scores[doc_id] = {
                'data': result,
                'vector_score': score,
                'vector_rank': rank + 1,
                'keyword_score': 0,
                'keyword_rank': 999
            }

        # Add keyword results
        for rank, result in enumerate(keyword_results):
            doc_id = result.get('id', str(result))
            if doc_id in combined_scores:
                combined_scores[doc_id]['keyword_score'] = 1.0
                combined_scores[doc_id]['keyword_rank'] = rank + 1
            else:
                combined_scores[doc_id] = {
                    'data': result,
                    'vector_score': 0,
                    'vector_rank': 999,
                    'keyword_score': 1.0,
                    'keyword_rank': rank + 1
                }

        # Calculate RRF score
        k = 60  # RRF constant
        for doc_id in combined_scores:
            item = combined_scores[doc_id]
            rrf_score = (1 / (k + item['vector_rank'])) + (1 / (k + item['keyword_rank']))
            item['final_score'] = rrf_score

        # Sort by final score
        ranked = sorted(combined_scores.values(), key=lambda x: x['final_score'], reverse=True)

        # Return top k
        results = []
        for item in ranked[:top_k]:
            result = item['data'].copy()
            result['_score'] = item['final_score']
            result['_vector_score'] = item['vector_score']
            result['_keyword_score'] = item['keyword_score']
            results.append(result)

        return results

    def find_similar_inspections(self, inspection_id: int, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find inspections similar to a given one

        Args:
            inspection_id: ID of the reference inspection
            top_k: Number of similar results

        Returns:
            List of similar inspections
        """
        if self.inspection_index is None:
            return []

        # Find the reference inspection
        ref_idx = None
        for idx, insp in enumerate(self.inspection_metadata):
            if insp.get('id') == inspection_id:
                ref_idx = idx
                break

        if ref_idx is None:
            return []

        # Get its embedding
        ref_embedding = self.inspection_index[ref_idx]

        # Find similar ones
        similarities = self._cosine_similarity(ref_embedding, self.inspection_index)

        # Get top k (excluding itself)
        top_indices = np.argsort(similarities)[::-1][1:top_k + 1]

        results = []
        for idx in top_indices:
            result = self.inspection_metadata[idx].copy()
            result['_score'] = float(similarities[idx])
            results.append(result)

        return results

    @staticmethod
    def _cosine_similarity(vec1, vec2_matrix):
        """
        Calculate cosine similarity between vector and matrix

        Args:
            vec1: Query vector (1D)
            vec2_matrix: Matrix of vectors (2D)

        Returns:
            Array of similarity scores
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
        vec2_norms = vec2_matrix / (np.linalg.norm(vec2_matrix, axis=1, keepdims=True) + 1e-10)

        # Dot product = cosine similarity for normalized vectors
        similarities = np.dot(vec2_norms, vec1_norm)

        return similarities

    def save_index(self, filepath: str):
        """Save index to file"""
        data = {
            'inspection_index': self.inspection_index.tolist() if self.inspection_index is not None else None,
            'inspection_metadata': self.inspection_metadata,
            'document_index': self.document_index.tolist() if self.document_index is not None else None,
            'document_metadata': self.document_metadata,
            'model_name': self.model_name
        }

        import pickle
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)

        print(f"✅ Index saved to {filepath}")

    def load_index(self, filepath: str):
        """Load index from file"""
        import pickle
        with open(filepath, 'rb') as f:
            data = pickle.load(f)

        if data['inspection_index'] is not None:
            self.inspection_index = np.array(data['inspection_index'])
        self.inspection_metadata = data['inspection_metadata']

        if data['document_index'] is not None:
            self.document_index = np.array(data['document_index'])
        self.document_metadata = data['document_metadata']

        print(f"✅ Index loaded from {filepath}")
        print(f"   Inspections: {len(self.inspection_metadata)}")
        print(f"   Documents: {len(self.document_metadata)}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics"""
        return {
            'model': self.model_name,
            'model_loaded': self.model is not None,
            'inspections_indexed': len(self.inspection_metadata),
            'documents_indexed': len(self.document_metadata),
            'vector_dimension': self.inspection_index.shape[1] if self.inspection_index is not None else 0
        }


# Example usage
if __name__ == "__main__":
    print("Vector Search Engine (Level 3)")
    print("=" * 60)
    print("\nFeatures:")
    print("  ✓ Semantic similarity search")
    print("  ✓ Multi-lingual (Thai + English)")
    print("  ✓ Hybrid search (vector + keyword)")
    print("  ✓ Find similar items")
    print("\nModel: paraphrase-multilingual-mpnet-base-v2")
    print("=" * 60)
