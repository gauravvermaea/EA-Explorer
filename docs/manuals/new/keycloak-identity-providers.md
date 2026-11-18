---
title: Signing in with Entra ID, Google or another identity provider
summary: Keycloak brokers sign-in to the organisation's own provider; EA Explorer still gives roles from groups.
new: written for the printed guides (owner, 18 Nov 2026, 19:5x: "Write new sections"); to be checked by the owner
---

## How it fits together

People never sign in to EA Explorer directly: they sign in to **Keycloak**, which runs beside EA Explorer in the realm
`eaexplorer`, and Keycloak tells EA Explorer who they are and which groups they are in. Keycloak can keep its own
accounts, read them from Active Directory or LDAP (the chapter before), or hand the sign-in to another **identity
provider**: Microsoft Entra ID, Google, or any provider that speaks **OpenID Connect** or **SAML 2.0**. This is called
*brokering*: the person picks the provider on Keycloak's sign-in page (or is sent straight to it), signs in there, and
comes back to EA Explorer signed in.

Whatever the provider, the roles work the same way: EA Explorer reads the person's **groups** from the `groups` claim
and gives the global role each group is mapped to (**System Admin › Users and roles › Keycloak role mapping**). So for
each provider there are two jobs: let people sign in, and get their groups into Keycloak.

> **Before you start** You need the Super Admin role, and access to Keycloak's admin console at
> `https://<your EA Explorer address>/auth/admin` (realm `eaexplorer`). You also need someone who can register an
> application with the provider (for Entra ID, an Entra administrator; for Google, a Google Cloud project owner).

Every provider needs EA Explorer's **redirect address**, the place it sends people back to after they sign in:

```
https://<your EA Explorer address>/auth/realms/eaexplorer/broker/<alias>/endpoint
```

`<alias>` is the short name you give the provider in Keycloak (for example `entra` or `google`). Keycloak shows the
exact address on the provider's page as **Redirect URI**: copy it from there.

## Microsoft Entra ID

1. **In Entra ID**, register an application (App registrations › New registration). Give it a name such as
   *EA Explorer*, choose who may sign in (usually this organisation only) and set the **redirect URI** (type Web) to
   Keycloak's redirect address above, with the alias `entra`.
2. Under **Certificates & secrets**, make a client secret and copy its value; under **Overview**, copy the
   **Application (client) ID** and the **Directory (tenant) ID**.
3. Under **Token configuration**, **Add groups claim**: choose the groups to send (security groups, or the groups
   assigned to the application) and, for the ID token, **sAMAccountName** or **Group ID**. Entra ID sends group object
   IDs unless it is told to send names.
4. **In Keycloak**, open the realm `eaexplorer`, **Identity providers › Microsoft** (or **OpenID Connect v1.0**), with
   the alias `entra`. Paste the client ID and secret; for OpenID Connect, the discovery address is
   `https://login.microsoftonline.com/<tenant ID>/v2.0/.well-known/openid-configuration`. Save.
5. On the provider's **Mappers** tab, add a mapper that brings the groups across: **Advanced Claim to Group** (one per
   Entra group, putting the person in the Keycloak group of the same name) or **Claim to Role**. The realm's own
   "directory groups" mapper then sends them to EA Explorer as `groups`.
6. **In EA Explorer**, map each group to its role: **System Admin › Users and roles › Keycloak role mapping**, choose
   **Directory group**, type the group's name (or its Entra object ID) and pick the role.

## Google

1. **In Google Cloud**, open the project's **APIs & Services › Credentials**, **Create credentials › OAuth client ID**,
   type **Web application**. Add Keycloak's redirect address (alias `google`) as an **authorised redirect URI**. Copy
   the client ID and secret. (Set up the OAuth consent screen first if the project asks.)
2. **In Keycloak**, **Identity providers › Google**, alias `google`: paste the client ID and secret. To let in only the
   organisation's own Google Workspace accounts, set **Hosted domain** to its domain (for example `example.com`). Save.
3. **Groups:** Google does not send group memberships when people sign in. Put people in Keycloak groups another way:
   a **Hardcoded group** mapper on the provider (everyone who signs in with Google joins one group, for example
   *Architects*), or add them to groups by hand in Keycloak (**Users › the person › Groups**).
4. **In EA Explorer**, map those Keycloak groups to roles as for Entra ID.

## Any OpenID Connect provider

Okta, Ping, Auth0, AWS Cognito and most others speak OpenID Connect.

1. **At the provider**, register a web application with Keycloak's redirect address (choose an alias such as `okta`),
   and copy its client ID, client secret and **discovery address** (it ends in `/.well-known/openid-configuration`).
2. **In Keycloak**, **Identity providers › OpenID Connect v1.0**: the alias, the discovery address (Keycloak fills in
   the rest), the client ID and secret, client authentication *Client secret sent as post* unless the provider says
   otherwise. Save.
3. If the provider can send groups, ask it for a `groups` claim and add an **Advanced Claim to Group** or
   **Claim to Role** mapper; if not, use a **Hardcoded group** mapper or add people to groups in Keycloak.
4. Map the groups to roles in EA Explorer.

## A SAML 2.0 provider

1. **In Keycloak**, **Identity providers › SAML v2.0**, with an alias. Give the provider's **metadata address** (or
   upload its metadata file); Keycloak fills in the single sign-on address and its certificate. Save, then give the
   provider Keycloak's own metadata, shown on the same page (**SAML entity descriptor**).
2. **At the provider**, add Keycloak as a service provider from that metadata, and have it send the person's groups
   as an attribute.
3. In Keycloak add an **Advanced Attribute to Group** mapper for that attribute, then map the groups to roles in EA
   Explorer.

## Good practice

- **Keep one way in that does not depend on the provider.** Keycloak's own administrator account and EA Explorer's
  break-glass sign-in still work when the provider is down; keep their details safe (see the Emergency guide).
- **Send people straight to the provider.** When everyone uses it, set it as Keycloak's default
  (**Authentication › browser › Identity Provider Redirector**, with the alias), so they do not see Keycloak's own form.
- **Map groups, not people.** Roles that come from groups follow the directory: someone who leaves the group loses the
  role at their next sign-in. Roles on a model or a project are still given on its People tab.
- **Multi-factor sign-in.** If the provider already asks for a second factor, EA Explorer's own multi-factor sign-in
  can stay off for those people; if not, turn it on (**System Admin › Security**).
- **Test with one person first**, in a private browser window, before telling everyone.
