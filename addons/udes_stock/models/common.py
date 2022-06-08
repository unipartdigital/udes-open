import re


from odoo import _
from odoo.exceptions import UserError

MAX_SEQUENCE = 999  # Default maximum sequence number allowed


def get_next_name(obj, code, sequence=None):
    """
    Get the next name for an object.
    For when we want to create an object whose name links back to a previous
    object.  For example BATCH/00001-002.
    Assumes original names are of the form `r".*\d+"`.
    The amount of padding is determined from the variable MAX_SEQUENCE, we
    might want to make this model specific so different models can be configured
    differently.

    Arguments:
        obj - the source object for the name
        code - the code for the object's model in the ir_sequence table
        sequence - the relevant ir sequence to use
    Returns:
        The generated name, a string.
    """
    IrSequence = obj.env["ir.sequence"]

    if not sequence:
        # Use the IrSequence code in 14 approach.
        # Return False if no sequence found to be consistent with Odoo Core.
        obj.check_access_rights("read")
        force_company = obj._context.get("force_company")
        if not force_company:
            force_company = obj.env.user.company_id.id

        seq_ids = IrSequence.search(
            [("code", "=", code), ("company_id", "in", [force_company, False])], order="company_id"
        )
        if not seq_ids:
            return False
        ir_sequence = seq_ids[0]
    else:
        ir_sequence = sequence

        # In the case when we want to sequence an object within a model,
        # for example a picking, we search for the last record that has
        # a similar name. We cannot rely on the sequence, as the obj may exist
        # in a tree and may be closer to the source node. For example in pickings,
        # we may be creating the 10th backorder from PICK0002, sequencing would give
        # PICK0002-0001, we want PICK0002-0010.
        ObjModel = obj
        base_name = obj.name.split("-")[0]
        obj = ObjModel.search(
            [("name", "=ilike", base_name + "%")], limit=1, order="id Desc")

    # Determine the amount of padding from the maximum sequence value
    # Note: This assumes a sensible MAX_SEQUENCE value, i.e integer.
    padding = len(str(MAX_SEQUENCE))

    # Name pattern for continuation object.
    name_pattern = r"({}[0-9]+)-([0-9]{{{padding}}})".format(
        re.escape(ir_sequence.prefix), padding=padding
    )

    match = re.match(name_pattern, obj.name)
    if match:
        root = match.group(1)
        new_sequence = int(match.group(2)) + 1
        # If the sequence exceeds 999 then raise a more visible error rather than
        # picking already exists.
        if new_sequence > MAX_SEQUENCE:
            raise UserError(
                _(
                    """
            Trying to create a backorder with sequence %d
            but this exceeds the maximum allowed %d
            """
                )
                % (new_sequence, MAX_SEQUENCE)
            )
    else:
        # This must be the original object.
        root = obj.name
        new_sequence = 1
    return f"{root}-{new_sequence:0>{padding}}"
