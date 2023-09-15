FROM unipartdigital/udes-tester:14.0

# Prerequisite module download
ADD https://codeload.github.com/unipartdigital/odoo-package-hierarchy/zip/${ODOO_VERSION} \
    /opt/odoo-package-hierarchy.zip
USER root
RUN unzip -q -d /opt /opt/odoo-package-hierarchy.zip ; \
    ln -s /opt/odoo-package-hierarchy-${ODOO_VERSION}/addons/* \
          /opt/odoo/addons/

# psycopg2-binary dependencies
RUN apt update && apt install -y python3-dev libpq-dev
# install pip packages
USER odoo
RUN pip3 install --user \
    coverage==4.5.1 \
    psycopg2-binary==2.8.5 \
    # TODO: Werkzeug version needs to be reverted from 2.3.7 for some udes_security tests to pass.
    # See https://taiga.unipart.digital/project/udes-x/issue/5161
    Werkzeug==0.16.1

# Add modules
USER root
ADD addons /opt/odoo-addons

# Module installation (without tests)
RUN odoo-wrapper --without-demo=all -i \
    udes_common,udes_get_info,udes_security,udes_stock,udes_stock_packaging,udes_stock_refactoring,udes_stock_routing,udes_suggest_location,udes_stock_picking_batch

# Module tests
CMD ["--test-enable", "-i", "udes_common,udes_get_info,udes_security,udes_stock,udes_stock_packaging,udes_stock_refactoring,udes_stock_routing,udes_suggest_location,udes_stock_picking_batch"]

# Skip modules that depend on external modules
# - udes_sale_stock
# - edi_notifier
# - udes_stock_cron
