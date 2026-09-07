"""ChromaDB client for olympiad problem retrieval.

Loads Qwen3-Embedding-0.6B from ModelScope cache (CPU) and queries the
pre-built ChromaDB index. Returns top-k similar problems+solutions.
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Optional

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")


class DatabaseClient:
    """Client for querying olympiad problem database via ChromaDB."""

    def __init__(
        self,
        db_dir: str = "database",
        collection_name: str = "olympiad_problems",
        model_id: str = "Qwen/Qwen3-Embedding-0.6B",
        device: str = "cpu",
    ):
        """Initialize the database client.

        Args:
            db_dir: path to ChromaDB directory (relative to project root)
            collection_name: ChromaDB collection name
            model_id: embedding model ID (ModelScope)
            device: "cpu" or "cuda"
        """
        self.db_dir = Path(db_dir)
        # 相对路径按项目根解析（不依赖 cwd）：本文件位于 utils/retrieval/ 下，
        # 项目根是三层 parent，与 tfidf_client 的语料路径解析一致。
        if not self.db_dir.is_absolute():
            self.db_dir = Path(__file__).resolve().parent.parent.parent / self.db_dir
        self.collection_name = collection_name
        self.model_id = model_id
        self.device = device
        self._model = None
        self._collection = None

    def _load_model(self):
        """Lazy-load embedding model from ModelScope cache."""
        if self._model is not None:
            return

        from sentence_transformers import SentenceTransformer

        # Resolve model directory from ModelScope cache
        model_dir = self._resolve_model_dir()
        self._model = SentenceTransformer(
            str(model_dir), device=self.device, trust_remote_code=True
        )

    def _resolve_model_dir(self) -> Path:
        """Find model in project directory or ModelScope cache."""
        # Priority 1: Project-local model directory
        project_model = Path(__file__).parent.parent.parent / "models" / "Qwen3-Embedding-0.6B" / "snapshots" / "master"
        if (project_model / "config.json").exists():
            return project_model

        # Priority 2: Try ModelScope download/cache
        try:
            from modelscope import snapshot_download
            return Path(snapshot_download(self.model_id))
        except Exception:
            pass

        # Priority 3: Known cache paths
        for cand in (
            Path.home() / ".cache/modelscope/models/Qwen--Qwen3-Embedding-0.6B/snapshots/master",
            Path.home() / ".cache/modelscope/hub/Qwen/Qwen3-Embedding-0.6B",
        ):
            if (cand / "config.json").exists():
                return cand

        raise FileNotFoundError(
            f"Model {self.model_id} not found. Expected locations:\n"
            f"  1. Project-local: {project_model}\n"
            f"  2. ModelScope cache: ~/.cache/modelscope/\n"
            "To download: pip install modelscope && python -c "
            "\"from modelscope import snapshot_download; "
            "snapshot_download('Qwen/Qwen3-Embedding-0.6B')\""
        )

    def _load_collection(self):
        """Lazy-load ChromaDB collection."""
        if self._collection is not None:
            return

        import chromadb

        if not (self.db_dir / "chroma.sqlite3").exists():
            raise FileNotFoundError(
                f"ChromaDB not found at {self.db_dir}. "
                "Run 'git lfs pull' to fetch chroma.sqlite3 (tracked by Git LFS)."
            )

        client = chromadb.PersistentClient(path=str(self.db_dir))
        self._collection = client.get_collection(self.collection_name)

    def query(self, problem: str, top_k: int = 3) -> List[Dict[str, any]]:
        """Query database for similar problems+solutions.

        Args:
            problem: problem text (query)
            top_k: number of results to return

        Returns:
            List of dicts with keys:
                - problem: problem text
                - solution: solution text
                - similarity: cosine similarity (0-1)
                - source: source file path
                - contest: contest name
                - year: year (if available)
        """
        self._load_model()
        self._load_collection()

        # Encode query
        vec = self._model.encode(
            [problem], normalize_embeddings=True, convert_to_numpy=True
        )[0].tolist()

        # Query ChromaDB
        res = self._collection.query(
            query_embeddings=[vec],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        # Parse results
        results = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            problem_text, solution_text = self._parse_document(doc)
            results.append({
                "problem": problem_text,
                "solution": solution_text,
                "similarity": 1 - dist,  # cosine distance -> similarity
                "source": meta.get("source", ""),
                "contest": meta.get("contest", ""),
                "year": meta.get("year", ""),
            })

        return results

    @staticmethod
    def _parse_document(doc: str) -> tuple[str, str]:
        """Parse a document into (problem, solution) pair.

        Documents are stored as:
            ## Problem
            <problem text>

            ## Solution
            <solution text>
        """
        prob_match = re.search(
            r'## Problem\s*(.*?)(?=## Solution|\Z)',
            doc, re.DOTALL | re.IGNORECASE
        )
        sol_match = re.search(
            r'## Solution\s*(.*?)(?=## Problem|\Z)',
            doc, re.DOTALL | re.IGNORECASE
        )

        problem = prob_match.group(1).strip() if prob_match else ""
        solution = sol_match.group(1).strip() if sol_match else ""

        return problem, solution
