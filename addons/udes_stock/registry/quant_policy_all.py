from .quant_policy import QuantPolicy


class QuantPolicyAll(QuantPolicy):

    @classmethod
    def name(cls):
        """Set code name of the quant policy."""
        return "all"

    @classmethod
    def description(cls):
        """Set description of the quant policy."""
        return "Allow all"

    def apply_location_quant_policy(self, location):
        """No specific policy related checks at the moment."""
        pass
