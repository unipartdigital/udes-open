# -*- coding: utf-8 -*-

def transform_id_fields(input_dict, fields):
    """ Transform the id fields info from id+name to only id
    """
    for field in fields:
        if field in input_dict and input_dict[field]:
            input_dict[field]=input_dict[field][0]

    return input_dict
