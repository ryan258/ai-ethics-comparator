"""
Reporting Module - Arsenal Module
Handles PDF generation for experimental runs
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from jinja2 import Environment, FileSystemLoader
except ModuleNotFoundError:  # pragma: no cover - optional dependency guard
    Environment = None  # type: ignore[assignment]
    FileSystemLoader = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

try:
    from weasyprint import HTML
except (ModuleNotFoundError, OSError) as exc:  # pragma: no cover - optional dependency guard
    HTML = None  # type: ignore[assignment]
    WEASYPRINT_IMPORT_ERROR: Exception | None = exc
else:  # pragma: no cover - import side effect only
    WEASYPRINT_IMPORT_ERROR = None

class ReportGenerator:
    """Generates PDF reports from run data"""

    def __init__(self, templates_dir: str = "templates") -> None:
        if Environment is None or FileSystemLoader is None:
            raise RuntimeError("jinja2 is required to generate reports.")

        self.templates_dir = Path(templates_dir)
        if not self.templates_dir.exists():
            raise ValueError(f"Templates directory not found: {templates_dir}")
            
        self.env = Environment(loader=FileSystemLoader(str(self.templates_dir)))
        self.template_name = "reports/pdf_report.html"
        self.pdf_available = HTML is not None
        
        # Validate template exists
        try:
            self.env.get_template(self.template_name)
        except Exception as e:
            raise ValueError(f"PDF template not found: {self.template_name}") from e

    def generate_pdf_report(
        self, 
        run_data: Dict[str, Any], 
        paradox: Dict[str, Any], 
        insight: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """
        Generate PDF report binary
        
        Args:
            run_data: Complete run data
            paradox: Paradox definition
            insight: Optional analysis insight
            
        Returns:
            PDF bytes
        """
        if HTML is None:
            raise RuntimeError(
                "PDF generation is unavailable because WeasyPrint could not load its optional "
                "native dependencies."
            ) from WEASYPRINT_IMPORT_ERROR

        try:
            template = self.env.get_template(self.template_name)
            
            # Prepare context
            context = {
                "run": run_data,
                "paradox": paradox,
                "insight": insight,
                "generated_at": run_data.get("timestamp")
            }
            
            # Render HTML
            html_content = template.render(**context)
            
            # Generate PDF
            # Use base_url to allow resolving static assets if needed
            # For now, we'll embed CSS directly or use minimal styling
            return HTML(string=html_content).write_pdf()
            
        except Exception as e:
            logger.error(f"PDF Generation failed: {e}")
            raise
