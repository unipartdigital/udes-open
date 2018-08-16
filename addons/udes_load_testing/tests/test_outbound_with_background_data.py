# -*- coding: utf-8 -*-

from .common import BackgroundDataRunner, parameterized
from .config import config
from .test_outbound import OutboundLines, OutboundMoves


class TestOutboundLinesBackGroundData(BackgroundDataRunner, OutboundLines):

    @parameterized.expand(config.TestOutboundLinesBackGroundData
                          or config.default)
    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()


class TestOutboundMovesBackGroundData(BackgroundDataRunner, OutboundMoves):

    @parameterized.expand(config.TestOutboundMovesBackGroundData
                          or config.default)
    def test_outbound_pick(self, n):
        self._outbound_pick(n)

    def test_report(self):
        self._report()
