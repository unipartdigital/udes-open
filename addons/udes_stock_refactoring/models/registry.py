# -*- coding: utf-8 -*-
from abc import ABCMeta
from addons.udes_common.models.models import groupby


class RegistryMeta(ABCMeta):

    udes_registry = {}

    def __init__(cls, name, bases, dict):
        super(RegistryMeta, cls).__init__(name, bases, dict)
        refactor_action_name = cls.name()

        if not refactor_action_name:
            return

        if (
            refactor_action_name in cls.udes_registry
            and cls.udes_registry[refactor_action_name] is not cls
        ):
            raise ValueError("Name ({}) is already taken".format(refactor_action_name))

        cls.udes_registry[refactor_action_name] = cls
        # Check it has a valid interface
        cls(object)
        setattr(cls, groupby.__name__, groupby)
