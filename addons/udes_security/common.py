from odoo.http import request
import re


# Replaces redirect param with None if it's going external
def remove_external_redirect(redirect):
    base_location = request.httprequest.url_root.rstrip('/')
    # If the URL doesn't begin with the current url root
    if redirect:
        if not redirect.startswith(base_location):
            # If the URL is not relative e.g. http://somewhere.com
            if re.match(r'^(?:([A-Za-z]*:?/{2,})|([A-Za-z]+:/)|(\\{2,}))', redirect):
                redirect = None
    return redirect
