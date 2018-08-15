from .common import BackgroundDataRunner, parameterized
from .test_picking import PickLines, PickMoves


class TestPickLinesBackGroundData(BackgroundDataRunner, PickLines):

    @parameterized.expand([(10,), (20,), (30,), (40,), (50,)] * 3)
    def test_picking(self, n):
        self._load_test_picking(n)

    def test_report(self):
        self._report()

class TestPickMovesBackGroundData(BackgroundDataRunner, PickMoves):

    @parameterized.expand([(10,), (20,), (30,), (40,), (50,)] * 3)
    def test_picking(self, n):
        self._load_test_picking(n)

    def test_report(self):
        self._report()
