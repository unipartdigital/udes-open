FROM unipartdigital/udes-tester:14.0

# Prerequisite module download
#
ADD https://codeload.github.com/unipartdigital/odoo-package-hierarchy/zip/${ODOO_VERSION} \
    /opt/odoo-package-hierarchy.zip
USER root
RUN unzip -q -d /opt /opt/odoo-package-hierarchy.zip ; \
    ln -s /opt/odoo-package-hierarchy-${ODOO_VERSION}/addons/* \
          /opt/odoo/addons/

# install psycopg2
USER odoo
RUN pip3 install psycopg2-binary==2.8.5 --user
# Add modules
#
USER root
ADD addons /opt/odoo-addons

# Module installation (without tests)
#
RUN odoo-wrapper --without-demo=all -i \
    udes_stock,udes_common,udes_stock_packaging

# Module tests
#
CMD ["--test-enable", "-i", "udes_stock,udes_common,udes_stock_packaging"]
