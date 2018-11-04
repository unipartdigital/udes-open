FROM unipartdigital/udes-tester

# Prerequisite module download
#
ADD https://codeload.github.com/unipartdigital/odoo-blocked-locations/zip/HEAD \
    /opt/odoo-blocked-locations.zip
ADD https://codeload.github.com/unipartdigital/odoo-package-hierarchy/zip/HEAD \
    /opt/odoo-package-hierarchy.zip
ADD https://codeload.github.com/unipartdigital/odoo-print/zip/HEAD \
    /opt/odoo-print.zip
ADD https://codeload.github.com/unipartdigital/odoo-edi/zip/HEAD \
    /opt/odoo-edi.zip
ADD https://codeload.github.com/OCA/server-auth/zip/HEAD \
    /opt/server-auth.zip
USER root
RUN unzip -q -d /opt /opt/odoo-blocked-locations.zip ; \
    unzip -q -d /opt /opt/odoo-package-hierarchy.zip ; \
    unzip -q -d /opt /opt/odoo-print.zip ; \
    unzip -q -d /opt /opt/odoo-edi.zip ; \
    unzip -q -d /opt /opt/server-auth.zip ; \
    ln -s /opt/odoo-blocked-locations-HEAD/addons/* \
          /opt/odoo-package-hierarchy-HEAD/addons/* \
          /opt/odoo-print-HEAD/addons/* \
          /opt/odoo-edi-HEAD/addons/* \
          /opt/server-auth-HEAD/password_security \
          /opt/odoo/addons/

# Add modules
#
ADD addons /opt/odoo-addons

# Module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i \
    udes_stock,udes_mrp,udes_purchase,udes_report,udes_transport_management,udes_security

# Module tests
#
CMD ["--test-enable", "-i", "udes_stock,udes_mrp,udes_purchase,udes_report,udes_transport_management,udes_security"]
