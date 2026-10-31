from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from app.extractors.client import GitHubClient

logger = logging.getLogger("gitpulse.extractor")


def parse_gh_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """Parses standard ISO 8601 GitHub datetime strings."""
    if not dt_str or not isinstance(dt_str, str):
        return None
    try:
        clean_str = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean_str)
    except Exception:
        return None


class BaseResourceExtractor(ABC):
    """
    Abstract base class for individual GitHub resource extractors.
    """

    def __init__(self, client: Optional[GitHubClient] = None):
        self.client = client or GitHubClient()

    @abstractmethod
    def extract(
        self,
        owner: str,
        repo: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extracts resource records from GitHub API for a given repository.
        Returns a list of normalized dictionary records ready for storage.
        """
        pass

