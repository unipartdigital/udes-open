from urllib.parse import urljoin
from itertools import groupby
from odoo import _

BASE_PRODUCT_IMAGE_URL = "/web/image/product.product/%i"

UDES_STATISTICS_LOG_FORMAT = "(%s) %s (%s) %s in %.2fs, %d queries, %.2f q/s"


def location_to_dict(location, **extras):
    """Represent a location in a format that json can understand"""
    if location.u_blocked:
        reason = location.u_blocked_reason or "no reason specified"
    else:
        reason = False

    loc = {
        "barcode": location.barcode,
        "name": location.name,
        "blocked": {"is_blocked": location.u_blocked, "reason": reason},
        "id": location.id,
        "storage_format": location.u_storage_format
    }
    loc.update(extras)
    return loc


def product_to_dict(product, **extras):
    """Represent a product in a format that json can understand"""
    prod = {"name": product.name, "barcode": product.barcode, "display_name": product.display_name}
    prod.update(extras)
    return prod


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


def product_quantity_label(product, quantity):
    """A function for a common output format for product quantity labels"""
    return "{name} x {quantity}".format(name=product.display_name, quantity=quantity)


def package_product_quantity_label(package, product, quantity):
    """A function for a common output format for package and product quantity labels"""
    return "{package} {product_quantity}".format(
        package=package.name, product_quantity=product_quantity_label(product, quantity)
    )


def batch_to_dict(batch):
    """Represent a batch in a format that json can understand"""
    return {"id": batch.id, "name": batch.u_original_name or batch.name}


def sorted_group_by(iterable, key):
    """Sorts and then groups an iterable by a key"""
    return groupby(sorted(iterable, key=key), key=key)


def product_image_urls(base_url, product):
    """Produces a product image urls object"""
    if product.image:
        base_url = urljoin(base_url, BASE_PRODUCT_IMAGE_URL % product.id)
        image_urls = {
            "large": base_url + "/image",
            "medium": base_url + "/image_medium",
            "small": base_url + "/image_small",
        }
        return image_urls
    return False


def md_format_label_value(label, value="", separator=":"):
    """Formats a label and value to markdown string: '**label:** value' """
    if label and value == "":
        md_string = f"**{_(label)}**\n"
    elif label == "" and value:
        md_string = f"{_(value)}\n"
    else:
        md_string = f"**{_(label)}{separator}** {_(value)}\n"
    return md_string


def md_format_list_of_label_value(label_value_list=None, separator=":"):
    """Formats the valuesd of a list of dictionaries
    with label and value keys into a markdown string."""
    if label_value_list is None:
        label_value_list = []
    md_format_label_value_string = ""
    for label_value_pairs in label_value_list:
        md_format_label_value_string += md_format_label_value(
            label_value_pairs["label"], label_value_pairs["value"], separator
        )
    return md_format_label_value_string


def format_dict_for_display_list_componet(dict_values):
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
