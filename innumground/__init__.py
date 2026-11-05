"""IN Number Grounding: check Indian money amounts (lakh, crore, Indian digit grouping) in an AI summary against its source."""
from .ground import check, extract, format_inr, indian_group

__version__ = "0.1.0"
__all__ = ["check", "extract", "format_inr", "indian_group", "__version__"]
