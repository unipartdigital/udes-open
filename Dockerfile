FROM unipartdigital/udes-tester:13.0

# Prerequisite module download
#
ADD https://codeload.github.com/unipartdigital/odoo-package-hierarchy/zip/${ODOO_VERSION} \
    /opt/odoo-package-hierarchy.zip
ADD https://codeload.github.com/unipartdigital/odoo-edi/zip/wip_13.0 \
    /opt/odoo-edi.zip
ADD https://codeload.github.com/OCA/server-auth/zip/${ODOO_VERSION} \
    /opt/server-auth.zip

USER root
RUN unzip -q -d /opt /opt/server-auth.zip ; \
    unzip -q -d /opt /opt/odoo-edi.zip    ; \
    unzip -q -d /opt /opt/odoo-package-hierarchy.zip    ; \
    ln -s /opt/server-auth-${ODOO_VERSION}/password_security \
          /opt/odoo-package-hierarchy-${ODOO_VERSION}/addons/* \
          /opt/odoo-edi-${ODOO_VERSION}/addons/* \
          /opt/server-auth-${ODOO_VERSION}/auth_brute_force \
          /opt/server-auth-${ODOO_VERSION}/auth_session_timeout \
          /opt/odoo/addons/

# Add modules
#
ADD addons /opt/odoo-addons

# Module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i udes_stock,udes_stock_move,udes_stock_refactoring

# Module tests
#
CMD ["--test-enable", "-i", "udes_stock,udes_stock_move,udes_stock_refactoring,udes_common"]
