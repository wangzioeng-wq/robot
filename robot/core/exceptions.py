class RobotError(Exception):
    """Base class for recoverable application errors."""


class ConfigurationError(RobotError):
    pass


class STTError(RobotError):
    pass


class LLMError(RobotError):
    pass


class TTSError(RobotError):
    pass


class AudioError(RobotError):
    pass
