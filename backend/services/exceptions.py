class ArchiveError(Exception):
    """Base exception for archive operations."""

    pass


class InvalidArchiveError(ArchiveError):
    """Raised when an archive is invalid, corrupted, or not found."""

    pass


class ArchiveSizeExceededError(ArchiveError):
    """Raised when an archive exceeds the maximum allowed extracted size."""

    pass


class ArchiveFileCountExceededError(ArchiveError):
    """Raised when an archive exceeds the maximum allowed number of files."""

    pass


class EmailParseError(Exception):
    """Raised when an email file cannot be read or parsed."""

    pass


class EmbeddingGenerationError(Exception):
    """Raised when embedding generation fails."""

    pass


class CalendarServiceError(Exception):
    """Raised when a calendar operation fails."""

    pass


class UnsafeCalendarTodoError(CalendarServiceError):
    """Raised when calendar todo text is unsafe for writeback."""

    pass
