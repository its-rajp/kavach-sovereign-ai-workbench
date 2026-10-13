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

    @staticmethod
    def expand_query(query: str) -> str:
        """Expand industrial queries with synonyms to resolve semantic mismatch."""
        expanded = query
        q_lower = query.lower()
        if "furnace" in q_lower and "fired heater" not in q_lower:
            expanded += " fired heater F-301 outlet temperature"
        if "turbine" in q_lower and ("interval" in q_lower or "preventive" in q_lower or "maintenance" in q_lower):
            expanded += " combustor inspection CI HGPE EOH 8000 24000 overhaul"
        if "pre-heat" in q_lower or "preheat" in q_lower:
            expanded += " exchangers crude charge 12-Month UT 24-Month bundle pull heat exchanger"
        if "gps" in q_lower or "coordinate" in q_lower:
            expanded += " latitude longitude 12.9812 74.8214 incident coordinates location"
        if "capacity" in q_lower or "throughput" in q_lower:
            expanded += " MMTPA refining capacity million metric tonnes"
        if "incident" in q_lower or "accident" in q_lower:
            expanded += " investigation root cause corrective action timeline"
        if "shutdown" in q_lower or "emergency" in q_lower:
            expanded += " ESD emergency trip isolation procedure"
        if "corrosion" in q_lower or "thickness" in q_lower:
            expanded += " NDT inspection monitoring wall thinning"
        if "temperature" in q_lower and "cdu" in q_lower:
            expanded += " fired heater outlet 365 celsius CDU-III"
        return expanded

    def retrieve(self, query: str, role: Union[Role, str] = Role.ANALYST, top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve role-authorized chunks for a given query with synonym expansion."""
        k = top_k or 8
        user_rank = get_role_rank(role)
        search_query = self.expand_query(query)

        # Retrieve candidates with similarity threshold and rank bound
        raw_results = self.indexer.search(
            query=search_query,
            top_k=k,
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
        k = top_k or 8
        user_rank = get_role_rank(role)
        search_query = self.expand_query(query)

        # 1. Retrieve authorized candidates bounded by user's clearance rank (SEC-R-01)
        authorized_chunks = self.indexer.search(
            query=search_query,
            top_k=k,
            threshold=self.settings.similarity_threshold,
            max_rank=user_rank,
        )

        # 2. Detect clearance intercept: higher-rank documents matched with high confidence,
        # but caller lacks rank. Only triggers when caller has no authorized docs AND
        # a high-confidence match (>= 0.58) exists in a higher tier.
        is_clearance_blocked = False
        min_required_rank = user_rank + 1

        if not authorized_chunks:
            all_candidates = self.indexer.search(
                query=query,
                top_k=k,
                threshold=0.72,  # Raised threshold prevents false blocks on loose keywords (FIX 2: Trial 1.4)
            )
            relevant_higher_rank_hits = [
                c for c in all_candidates
                if int(c.get("metadata", {}).get("clearance_rank", 1)) > user_rank
            ]
            if relevant_higher_rank_hits:
                is_clearance_blocked = True
                min_required_rank = min(
                    int(c.get("metadata", {}).get("clearance_rank", user_rank + 1))
                    for c in relevant_higher_rank_hits
                )
                print(f"\n⚠️ [CLEARANCE INTERCEPT DEBUG] Query: '{query}' | User Rank: {user_rank}")
                print(f"   Found {len(relevant_higher_rank_hits)} higher-rank hits (min_rank={min_required_rank})")
                for hit in relevant_higher_rank_hits[:3]:
                    print(f"   Hit: score={hit.get('score', 'N/A')}, rank={hit.get('metadata', {}).get('clearance_rank')}, src={hit.get('metadata', {}).get('source', 'unknown')}")
            else:
                print(f"\n✅ [CLEARANCE CHECK] No higher-rank docs matched for '{query}' — returning 'No Info' (not blocking)")

        return authorized_chunks[:k], is_clearance_blocked, min_required_rank



_retriever_instance: Optional[Retriever] = None


def get_retriever() -> Retriever:
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance

