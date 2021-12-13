FROM unipartdigital/udes-tester:14.0

# Prerequisite module download
#
ADD https://codeload.github.com/unipartdigital/odoo-package-hierarchy/zip/${ODOO_VERSION} \
    /opt/odoo-package-hierarchy.zip
USER root
RUN unzip -q -d /opt /opt/odoo-package-hierarchy.zip ; \
    ln -s /opt/odoo-package-hierarchy-{ODOO_VERSION}/addons/* \
          /opt/odoo/addons/

# Add modules
#
ADD addons /opt/odoo-addons

# Module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i \
    udes_stock,udes_common,

# Module tests
#
CMD ["--test-enable", "-i", "udes_stock,udes_common"]
