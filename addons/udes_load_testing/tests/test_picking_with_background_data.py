from .common import LoadRunner, parameterized
from .test_picking import TestPickLines, TestPickMoves


class TestPickLinesBackGroundData(TestPickLines):

    @classmethod
    def setUpClass(cls):
        super(TestPickLinesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()


class TestPickMovesBackGroundData(TestPickMoves):

    @classmethod
    def setUpClass(cls):
        super(TestPickMovesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()
