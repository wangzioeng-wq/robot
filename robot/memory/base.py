from abc import ABC, abstractmethod


class Memory(ABC):
    @abstractmethod
    def add_user_message(self, content):
        raise NotImplementedError

    @abstractmethod
    def add_assistant_message(self, content):
        raise NotImplementedError

    @abstractmethod
    def get_messages(self):
        raise NotImplementedError

    @abstractmethod
    def clear(self):
        raise NotImplementedError
