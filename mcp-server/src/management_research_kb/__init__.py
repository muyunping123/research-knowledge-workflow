"""Local research knowledge-base MCP server."""

from .config import Config, load_config
from .service import KnowledgeBaseService

__all__ = ["Config", "KnowledgeBaseService", "load_config"]
__version__ = "0.4.0"
