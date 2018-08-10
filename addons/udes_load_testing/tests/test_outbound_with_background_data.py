from .common import LoadRunner, parameterized
from .test_outbound import TestOutboundLines, TestOutboundMoves


class TestOutboundLinesBackGroundData(TestOutboundLines):

    @classmethod
    def setUpClass(cls):
        super(TestOutboundLinesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()


class TestOutboundMovesBackGroundData(TestOutboundMoves):

    @classmethod
    def setUpClass(cls):
        super(TestOutboundMovesBackGroundData, cls).setUpClass()
        cls._dummy_background_data()
