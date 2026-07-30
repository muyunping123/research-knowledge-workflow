"""Domain exceptions exposed as concise MCP tool errors."""


class KnowledgeBaseError(RuntimeError):
    """Base error for predictable knowledge-base failures."""


class ConfigError(KnowledgeBaseError):
    """Raised when configuration is missing or unsafe."""


class PathSafetyError(KnowledgeBaseError):
    """Raised when a requested path escapes an allowed root."""


class ZoteroUnavailable(KnowledgeBaseError):
    """Raised when the local Zotero API cannot be reached or parsed."""
