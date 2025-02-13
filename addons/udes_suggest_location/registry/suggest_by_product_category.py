from .suggest_locations_policy import SuggestLocationPolicy
from odoo.tools.translate import _


class ByProductCategory(SuggestLocationPolicy):
    """
    Find locations based on other places that product is stored and filtering by locations that
    are configured in product categories.

    Allows stock to be dropped in an empty location with the correct product
    category, even if the location has an orderpoint for a different product.
    """

    @classmethod
    def name(cls):
        return "by_product_category"

    def get_values_from_mls(self, mls):
        return {
            "product": mls.product_id.ensure_one(),
            "location": mls.picking_id.location_dest_id.ensure_one(),
            "location_ids": mls.product_id.categ_id.u_suggest_location_ids,
        }

    def _get_product_from_dict(self, values):
        """Get the product from the values, assumed ot be the int id of a product"""
        Product = self.env["product.product"]
        product_id = values.get("product_id")
        if not product_id:
            raise ValueError(_("No product found"))
        return Product.browse(product_id)

    def _get_picking_from_dict(self, values):
        """Get the picking from the values, assumed to be the int id of a picking"""
        Picking = self.env["stock.picking"]
        picking_id = values.get("picking_id")
        if not picking_id:
            raise ValueError(_("No picking found"))
        return Picking.browse(picking_id)

    def get_values_from_dict(self, values):
        picking = self._get_picking_from_dict(values)
        product = self._get_product_from_dict(values)
        return {
            "product": product,
            "location": picking.location_dest_id,
            "location_ids": product.categ_id.u_suggest_location_ids,
        }

    def get_policy_empty_location_domain(self, product, location, location_ids, **kwargs):
        policy_domain = super().get_policy_empty_location_domain(**kwargs)
        policy_domain += [("id" , "child_of" , location.id), ("id", "child_of", location_ids.ids)]
        return policy_domain

    def get_locations(self, product, location, location_ids, **kwargs):
        """
        Get product order point locations and all locations that are the location or child of its
        location with the same product and child of product category suggested locations.

        Prioritise first order point location if exists.
        """
        Quant = self.env["stock.quant"]
        OrderPoint = self.env["stock.warehouse.orderpoint"]
        product_category_locations_domain = [
            ("location_id", "child_of", location.id),
            ("product_id", "=", product.id),
            ("location_id", "child_of", location_ids.ids),
        ]

        # Add order="id" for performance as we don't care about the order
        product_orderpoints = OrderPoint.search(product_category_locations_domain, order="id")
        orderpoint_locations = product_orderpoints.location_id

        # Add order="id" for performance as we don't care about the order
        product_quants = Quant.search(product_category_locations_domain, order="id")
        quant_locations = product_quants.location_id

        locations = orderpoint_locations | quant_locations
        return locations

    def iter_mls(self, mls):
        for _prod, grouped_mls in mls.groupby("product_id"):
            yield grouped_mls



class ByProductCategoryOrderpoint(ByProductCategory):

    """
    Same with ByProductCategory, the only difference is on policy empty locations, this one will
    not suggest empty locations of expected locations which are order points of other products.

    Allows stock to be dropped in a location with the correct product
    category that: has stock for the product already, or has an orderpoint for the product,
    or an empty location with no orderpoints.
    """

    @classmethod
    def name(cls):
        return "by_product_category_orderpoint"

    def get_policy_empty_location_domain(self, product, location, location_ids, **kwargs):
        OrderPoint = self.env["stock.warehouse.orderpoint"]

        policy_domain = super().get_policy_empty_location_domain(product, location, location_ids, **kwargs)
        other_products_orderpoint_domain = [
            ("location_id", "child_of", location.id),
            ("product_id", "!=", product.id),
            ("location_id", "child_of", location_ids.ids),
        ]
        other_product_orderpoints = OrderPoint.search(other_products_orderpoint_domain, order="id")
        other_product_orderpoint_locations = other_product_orderpoints.location_id
        if other_product_orderpoint_locations:
            orderpoint_policy_domain = ["!", ("id", "child_of", other_product_orderpoint_locations.ids)]
            policy_domain += orderpoint_policy_domain
        return policy_domain
