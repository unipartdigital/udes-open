# -*- coding: utf-8 -*-
from abc import ABCMeta
from .models import groupby


class RegistryMeta(ABCMeta):

    udes_registry = {}

    def __init__(cls, name, bases, dict):
        super(RegistryMeta, cls).__init__(name, bases, dict)
        name = cls.name()

        if not name:
            return

        if (
            name in cls.udes_registry
            and cls.udes_registry[name] is not cls
        ):
            raise ValueError("Name ({}) is already taken".format(name))

        cls.udes_registry[name] = cls
        # Check it has a valid interface
        cls(object)
        setattr(cls, groupby.__name__, groupby)
