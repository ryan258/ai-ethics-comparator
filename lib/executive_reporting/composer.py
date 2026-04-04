"""
Composition interfaces for turning evidence into executive briefs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from lib.executive_reporting.models import EvidencePackage, ExecutiveBrief


class ExecutiveBriefComposer(ABC):
    """Domain-specific policy for converting evidence into a decision-ready brief."""

    @abstractmethod
    def compose(self, evidence: EvidencePackage) -> ExecutiveBrief:
        """Transform normalized evidence into an executive brief."""
