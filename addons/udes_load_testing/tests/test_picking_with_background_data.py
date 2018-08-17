# -*- coding: utf-8 -*-

from .common import BackgroundDataRunner, parameterized
from .test_picking import PickLines, PickMoves
from .config import config


class TestPickLinesBackGroundData(BackgroundDataRunner, PickLines):

    @parameterized.expand(config.TestPickLinesBackGroundData or config.default)
    def test_picking(self, n):
        self._load_test_picking(n)

    def test_report(self):
        self._report()

class TestPickMovesBackGroundData(BackgroundDataRunner, PickMoves):

    @parameterized.expand(config.TestPickMovesBackGroundData or config.default)
    def test_picking(self, n):
        self._load_test_picking(n)

    def test_report(self):
        self._report()
