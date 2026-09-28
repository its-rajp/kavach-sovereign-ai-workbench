"""Role-Aware Semantic Retriever for Kavach.

Implements SEC-R-01 (Least Privilege) and SEC-R-02 (Bounded Retrieval):
- Pulls candidate chunks up to top_k
- Filters candidate chunks by caller role clearance before handing to the LLM
"""

from typing import List, Dict, Any, Union, Optional, Tuple, TYPE_CHECKING
from ..security.rbac import filter_chunks_by_role, get_role_rank, Role
from ..config import get_settings

if TYPE_CHECKING:
    from ..ingestion.indexer import Indexer


class Retriever:
    """Retrieves document chunks grounded in user role clearance."""

    def __init__(self, indexer: Optional["Indexer"] = None):
        if indexer is None:
            from ..ingestion.indexer import get_indexer
            self.indexer = get_indexer()
        else:
            self.indexer = indexer
        self.settings = get_settings()

    def retrieve(self, query: str, role: Union[Role, str] = Role.ANALYST, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve role-authorized chunks for a given query."""
        k = top_k or self.settings.top_k
        user_rank = get_role_rank(role)

        # Retrieve candidates with similarity threshold and rank bound
        raw_results = self.indexer.search(
            query=query,
            top_k=k * 2,  # Fetch extra candidates to account for role filtering
            threshold=self.settings.similarity_threshold,
            max_rank=user_rank,
        )

        # Enforce Least Privilege (SEC-R-01): filter out chunks above caller's clearance
        authorized_chunks = filter_chunks_by_role(raw_results, role=role)

        # Enforce Bounded Retrieval (SEC-R-02): cap at top_k
        return authorized_chunks[:k]

    def retrieve_with_security_check(
        self,
        query: str,
        role: Union[Role, str] = Role.ANALYST,
        top_k: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], bool, int]:
        """Retrieve authorized chunks and detect if query targeted higher-clearance enclaves.

        Returns:
            (authorized_chunks, is_clearance_blocked, min_required_rank)
        """
        k = top_k or self.settings.top_k
        user_rank = get_role_rank(role)

        # 1. Unfiltered candidate search to detect any high-similarity hits across all vaults
        all_candidates = self.indexer.search(
            query=query,
            top_k=k * 2,
            threshold=self.settings.similarity_threshold,
        )

        # 2. Filter authorized candidates
        authorized_chunks = filter_chunks_by_role(all_candidates, role=role)

        # 3. Detect clearance intercept: higher-rank documents matched with high relevance, but user lacks rank
        is_clearance_blocked = False
        min_required_rank = user_rank + 1

        INTERCEPT_SIMILARITY_THRESHOLD = 0.58
        relevant_higher_rank_hits = [
            c for c in all_candidates
            if float(c.get("score", 0.0)) >= INTERCEPT_SIMILARITY_THRESHOLD
            and int(c.get("metadata", {}).get("clearance_rank", 1)) > user_rank
        ]

        if not authorized_chunks and relevant_higher_rank_hits:
            is_clearance_blocked = True
            min_required_rank = min(
                int(c.get("metadata", {}).get("clearance_rank", 3))
                for c in relevant_higher_rank_hits
            )

        # Fallback: if no authorized chunks but higher-rank chunks exist in the store,
        # flag as clearance-blocked even if similarity was too low to trigger the threshold.
        # This prevents the misleading "no info" message when data exists but is above the user's rank.
        if not authorized_chunks and not is_clearance_blocked:
            total_count = self.indexer.count()
            user_visible_count = self.indexer.count(max_rank=user_rank)
            if total_count > 0 and user_visible_count == 0:
                is_clearance_blocked = True
                min_required_rank = user_rank + 1

        return authorized_chunks[:k], is_clearance_blocked, min_required_rank



_retriever_instance: Optional[Retriever] = None


def get_retriever() -> Retriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance

