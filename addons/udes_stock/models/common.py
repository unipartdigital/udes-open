# -*- coding: utf-8 -*-

from collections import namedtuple
from enum import Enum

from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES

Priority = namedtuple('Priority', ['id', 'name'])


class PriorityGroups(Enum):
    Picking = 'Picking'


_PRIORITIES_BY_GROUP = {
    PriorityGroups.Picking: [Priority(*t) for t in PROCUREMENT_PRIORITIES]}


PRIORITIES = [(p.id, p.name)
              for priorities in _PRIORITIES_BY_GROUP.values()
              for p in priorities]

PRIORITY_GROUPS = {
    priority_group: {'name': priority_group.value,
                     'priorities': [p._asdict() for p in priorities]}
    for priority_group, priorities in _PRIORITIES_BY_GROUP.items()}
