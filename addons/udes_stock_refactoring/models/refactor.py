# -*- coding: utf-8 -*-
from abc import abstractmethod, abstractclassmethod
from .registry import RegistryMeta

REFACTOR_REGISTRY = dict()


class RefactorRegistryMeta(RegistryMeta):
    udes_registry = REFACTOR_REGISTRY


class Refactor(metaclass=RefactorRegistryMeta):
    def __init__(self, env):
        super().__init__()
        self.env = env

    @abstractclassmethod
    def name(cls):
        """
        The name of the refactor action.
        NOTE: Name must not be None for the action to be registered.
        """
        return None

    @abstractclassmethod
    def description(cls):
        """The title of refactor action displayed in Odoo UI."""
        return None

    @abstractmethod
    def do_refactor(self, moves):
        """Refactor action to be carried out on the supplied stock move records."""
        return


def get_selection(cls):
    name = cls.name()
    description = cls.description()
    return (name, description)
