from odoo import tools
import ast

DEFAULT_PARAMS = [(10,), (50,), (100,), (150,), (200,)]
DEFAULT_REPEATS = 3
DEFAULT_BACKGROUND = 100


class Config(object):

    def __init__(self):
        super(Config, self).__init__()

        self._options = tools.config.misc.get('udes_load_test', {})

        self.repeats = int(self._options.get('repeats', DEFAULT_REPEATS))

        self.params = self._options.get('default', DEFAULT_PARAMS)
        if isinstance(self.params, str):
            self.params = ast.literal_eval(self.params)
        self.params *= self.repeats

        self.background = int(self._options.get('background',
                                                DEFAULT_BACKGROUND))

    def __getattribute__(self, attr_name, *args):
        try:
            return super(Config, self).__getattribute__(attr_name, *args)

        except AttributeError as e:
            if attr_name.lower() in self._options:

                repeats = int(self._options.get(
                    attr_name.lower() + '_repeats', self.repeats))

                value = ast.literal_eval(
                    self._options[attr_name.lower()]) * repeats

                # Make it show if we need it again it isn't recalulated
                self.__setattr__(attr_name, value)
                return value
        else:
            # If we can find it in options raise origonal error
            raise e

    def get_background_N(self, classname):
        return self._options.get(classname + "_background", self.background)


config = Config()
