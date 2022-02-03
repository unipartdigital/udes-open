# UDES LDAP

This addon enables authenticating logins using LDAP.  It extends the core Odoo [auth_ldap](https://github.com/odoo/odoo/tree/11.0/addons/auth_ldap) and the OCA [auth_ldaps](https://github.com/OCA/server-auth/tree/11.0/auth_ldaps) addons.


## Functionality

This module overrides the existing model to use a user's own credentials to bind to the LDAP server, instead of using a service account. The user will log in with their LDAP user id (`uid`) and password, _not_ their email address.

## Configuration

- To access the configuration screen, go to either of
  - Settings / Users & Companies / LDAP Servers 
  - Inventory / Configuration / Settings / General Settings / LDAP Authentication
- Example values
  - **LDAP Server address**: `ldap.example.com`
  - **LDAP Server port**: `636`
  - **Use TLS**: `False`
  - **Use LDAPS**: `True`
  - **LDAP binddn format**: `uid=%s,cn=users,cn=accounts,dc=example,dc=com`
  - **LDAP base**: `dc=example,dc=com`
  - **LDAP filter**: `(&(uid=%s)(objectClass=person)(memberOf=cn=mygroup,cn=groups,cn=accounts,dc=example,dc=com))`

## Technical Notes

### Models

The `res_company_ldap` model is extended

|Field Name | Type | Description |
| --- | --- | --- |
| u_ldap_binddn_fmt | Char | printf-style format string for the Distinguished Name used to bind to the LDAP server |
| ldap_binddn | Char | This existing field is hidden, as we don't use it |
| ldap_password | Char | This existing field is hidden, as we don't use it |


### Security

By default, the configuration screen is accessible only by the Admin user and users in the Trusted User and Debug User groups.

LDAP installations are vulnerable to [injection](https://cheatsheetseries.owasp.org/cheatsheets/LDAP_Injection_Prevention_Cheat_Sheet.html) attacks (analogous to SQL injection).  The `uid` used at login time should be treated as untrusted input and escaped when used to bind to, or query against, the LDAP server. The [python-ldap](https://pypi.org/project/python-ldap/) package (installed by `auth_ldap`) provides functions to do the escaping.

See also the README files for `auth_ldap` and `auth_ldaps`.
