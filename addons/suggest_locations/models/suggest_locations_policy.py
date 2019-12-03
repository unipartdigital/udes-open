# -*- coding: utf-8 -*-

from abc import ABCMeta, abstractmethod, abstractclassmethod

SUGGEST_LOCATION_REGISTRY = dict()


class RegisterMeta(ABCMeta):
    def __init__(cls, name, bases, dict):
        super(RegisterMeta, cls).__init__(name, bases, dict)
        policy_name = cls.name()

        if not policy_name:
            return

        if (
            policy_name in SUGGEST_LOCATION_REGISTRY
            and SUGGEST_LOCATION_REGISTRY[policy_name] is not cls
        ):
            raise ValueError("Name ({}) is already taken".format(policy_name))

        SUGGEST_LOCATION_REGISTRY[policy_name] = cls

        # Check it has a valid interface
        instance = cls(object, False)


class SuggestLocationPolicy(metaclass=RegisterMeta):
    def __init__(self, env, _preprocessing):
        """Use preprocessing flag to raise error if policy should not be
        preprocessed
        """
        super().__init__()
        self.env = env

    @abstractmethod
    def get_values_from_mls(self, mls):
        """Find values based on the move lines instances"""
        return dict()

    @abstractmethod
    def get_values_from_dict(self, values):
        """Find values based on the dict passed from
            stock.move._prepare_move_line_vals
        """
        return dict()

    @abstractmethod
    def get_locations(self, **values):
        """Logic to find the locations based on values provided"""
        return self.env["stock.location"].browse()

    @abstractmethod
    def iter_mls(self, mls):
        """Iterator so sensibly group mls for the policy"""
        for _id, mls in self.groupby("id"):
            yield mls

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
