# -*- coding: utf-8 -*-
from abc import abstractmethod, abstractclassmethod
from addons.udes_common.models.registry import RegistryMeta

SUGGEST_LOCATION_REGISTRY = dict()


class SuggestRegistryMeta(RegistryMeta):

    udes_registry = SUGGEST_LOCATION_REGISTRY


class SuggestLocationPolicy(metaclass=SuggestRegistryMeta):
    def __init__(self, env):
        super().__init__()
        self.env = env

    @abstractmethod
    def get_values_from_mls(self, mls):
        """Find values based on the move lines instances"""
        return dict()

    @abstractmethod
    def get_values_from_dict(self, values):
        """Find values based on the dict passed from stock.move._prepare_move_line_vals"""
        return dict()

    @abstractmethod
    def get_locations(self, **values):
        """Logic to find the locations based on values provided"""
        Location = self.env["stock.location"]
        return Location.browse()

    @abstractmethod
    def iter_mls(self, mls):
        """Iterator so sensibly group mls for the policy"""
        for _id, grouped_mls in mls.groupby("id"):
            yield grouped_mls

    @abstractclassmethod
    def name(cls):
        """The name of the policy
        NOTE: Do not return None here if you want your policy to be used as it
        will not be registered
        """
        return None


def get_selection(cls):
    name = cls.name()
    return (name, " ".join(x.capitalize() for x in name.split("_")))
