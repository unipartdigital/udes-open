from odoo.tests import common


class CommonBase(common.SavepointCase):
    @classmethod
    def create_partner_category(cls, name, **kwargs):
        """Create and return a partner category record with the supplied name"""
        Category = cls.env["res.partner.category"]

        category_vals = {"name": name}
        category_vals.update(kwargs)

        return Category.create(category_vals)

    @classmethod
    def create_partner(cls, name, **kwargs):
        """Create and return a partner record with the supplied name"""
        Partner = cls.env["res.partner"]

        partner_vals = {"name": name}
        partner_vals.update(kwargs)

        return Partner.create(partner_vals)

    @classmethod
    def create_company_partner(cls, name, **kwargs):
        """Create and return a company partner record with the supplied name"""
        company_vals = {"company_type": "company"}
        company_vals.update(kwargs)
        return cls.create_partner(name, **company_vals)

    @classmethod
    def create_contacts_for_partner(cls, partner, no_of_contacts=1, **kwargs):
        """
        Create and return a number (`no_of_contacts`) of partner records and link them to
        supplied partner
        """
        Partner = cls.env["res.partner"]

        contacts = Partner.browse()
        for i in range(no_of_contacts):
            contact_no = i + 1
            contact_name = f"Contact {contact_no}"

            # Set title and category based on whether or not the contact number is even,
            # this is so that the relation fields can be used for grouping
            contact_no_even = contact_no % 2 == 0

            contact_vals = {
                "parent_id": partner.id,
                "title": cls.title_dr.id if contact_no_even else cls.title_prof.id,
                "category_id": [
                    (
                        6,
                        0,
                        cls.category_even.ids if contact_no_even else cls.category_odd.ids,
                    )
                ],
            }
            contact_vals.update(**kwargs)

            contacts += cls.create_partner(contact_name, **contact_vals)

        return contacts
