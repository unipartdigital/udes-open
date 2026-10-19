from abc import abstractclassmethod
from odoo.addons.udes_common.registry.registry import RegistryMeta

QUANT_POLICY_REGISTRY = dict()


class QuantPolicyRegistryMeta(RegistryMeta):
    udes_registry = QUANT_POLICY_REGISTRY


class QuantPolicy(metaclass=QuantPolicyRegistryMeta):
    def __init__(self, env):
        super().__init__()
        self.env = env

    @abstractclassmethod
    def name(cls):
        """
        The name of the quant policy.
        NOTE: Name must not be None in subclasses.
        """
        return None

    @abstractclassmethod
    def description(cls):
        """The title of quant policy displayed in Odoo UI."""
        return None

    @classmethod
    def get_quant_policy(cls, location):
        """Recursively resolves active policy class"""
        location.ensure_one()

        if location.u_quant_policy and (
            policy_cls := cls.udes_registry.get(location.u_quant_policy)
        ):
            return policy_cls

        if location.location_id:
            return cls.get_quant_policy(location.location_id)

        return None

    @classmethod
    def check_locations_quant_policy(cls, env, locations):
        for location in locations:
            if policy_cls := cls.get_quant_policy(location):
                policy_cls(env).apply_location_quant_policy(location)

    @abstractclassmethod
    def apply_location_quant_policy(cls, location):
        """Define quant policy related to location in the respective subclasses."""
        raise NotImplementedError


def get_selection(cls):
    name = cls.name()
    description = cls.description()
    return name, description
