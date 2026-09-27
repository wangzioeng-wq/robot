from abc import ABC, abstractmethod


class STTProvider(ABC):
    @abstractmethod
    async def listen(self, audio_source=None, on_partial=None):
        raise NotImplementedError
