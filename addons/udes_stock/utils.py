from odoo import _
from odoo.tools.image import image_data_uri

UDES_STATISTICS_LOG_FORMAT = "(%s) %s (%s) %s in %.2fs, %d queries, %.2f q/s"


def product_quantity_label(product, quantity):
    """A function for a common output format for product quantity labels"""
    return "{name} x {quantity}".format(name=product.display_name, quantity=quantity)


def package_product_quantity_label(package, product, quantity):
    """A function for a common output format for package and product quantity labels"""
    return "{package} {product_quantity}".format(
        package=package.name, product_quantity=product_quantity_label(product, quantity)
    )


def format_picking_data_for_display_list_component(picking, order=True):
    """Formats the data of a picking to be displayed in a list component

    The data will be returned as a list of strings "packagename productname x productquantity"
    """
    contents = []
    for package, package_lines in picking.move_line_ids.groupby("package_id", order):
        for product, product_lines in package_lines.groupby("product_id", order):
            contents.append(
                package_product_quantity_label(
                    package, product, int(sum(product_lines.mapped("product_uom_qty")))
                )
            )
    return contents


def product_image_uris(product):
    """
    Produces a product image uris object.
    Each value is a base64 encoded `data:image/<format>;base64,<b64>` string
    """
    if product.image_1920:
        # NB: all fields: [image_1920, image_1024, image_512, image_256, image_128]
        # If image is smaller than fields res, then the field will just show the smaller image.
        return {
            "large": image_data_uri(product.image_1920),
            "medium": image_data_uri(product.image_512),
            "small": image_data_uri(product.image_128),
        }
    return False


def md_format_label_value(label, value="", separator=":"):
    """Formats a label and value to markdown string: '**label:** value'"""
    if label and value == "":
        md_string = f"**{_(label)}**\n"
    elif label == "" and value:
        md_string = f"{_(value)}\n"
    else:
        md_string = f"**{_(label)}{separator}** {_(value)}\n"
    return md_string


def md_format_list_of_label_value(label_value_list=None, separator=":"):
    """Formats the values of a list of dictionaries
    with label and value keys into a markdown string."""
    if label_value_list is None:
        label_value_list = []
    md_format_label_value_string = ""
    for label_value_pairs in label_value_list:
        md_format_label_value_string += md_format_label_value(
            label_value_pairs["label"], label_value_pairs["value"], separator
        )
    return md_format_label_value_string


def format_dict_for_display_list_component(dict_values):
    """
    Formats a dictionary into a list of key: value strings
    with the key in bold for use in display list components.
    """
    result = []
    if dict_values:
        for key, value in dict_values.items():
            temp_val = str(value) if str(value) != "False" else "None"
            result.append("**" + str(key) + "**" + ": " + temp_val)
    return result
