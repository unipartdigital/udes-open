from .common import BackgroundDataRunner, parameterized
from .test_outbound import OutboundLines, OutboundMoves


class TestOutboundLinesBackGroundData(BackgroundDataRunner, OutboundLines):

    @parameterized.expand([(10,), (20,), (30,), (40,), (50,)] * 3)

    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()


class TestOutboundMovesBackGroundData(BackgroundDataRunner, OutboundMoves):

    @parameterized.expand([(10,), (20,), (30,), (40,), (50,)] * 3)
    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()
