# The passwords

Every password and key is made strong and random when the settings are made (`eax init`), and kept in
`work/eaexplorer.env`, readable by its owner only. None is ever written to a log; the deploy page's scripts never
hold one.

| Command | Shows |
|---|---|
| `./eax.sh logins --admins` | the admin accounts: EA Explorer's Super Admin, Keycloak's administrator, the **break-glass** account (to sign in when Keycloak is down), Jenkins' administrator when Jenkins is on |
| `./eax.sh logins` | every user name and password |

On a server they ask you to type YES first, show the passwords on the screen only, and the audit log keeps who looked
and when. Only someone who can read the settings file can see them. Save the admin and break-glass passwords in your
password manager, and keep the break-glass one somewhere safe off the machine.

`./eax.sh secrets show` lists every password by name with its age and when it is next changed (never its value);
`./eax.sh secrets rotate <name>` changes one now.
