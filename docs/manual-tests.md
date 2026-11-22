# Checks done by hand

What the automated tests cannot do, each with the steps and a box to tick. A working record: the testing guide takes
these over when the documents are brought up to date (Release 14, D850).

## R9.7 Set up the authenticator again, from the user list (D829)

A phone with an authenticator app is needed (the owner, 21 Nov 2026: "This will have to be tested manually").
Two people: an admin (a User Admin or Super Admin) and a test person with an authenticator already set up.

- [ ] As the admin: System Admin › Users › People shows the test person's **Authenticator** as *set up*.
- [ ] The test person is signed in (in another browser), with Reports open too.
- [ ] The admin ticks the test person, chooses **Set up the authenticator again...**; the pop-up names them and says
      what will happen; **Ask**: it says *Asked: <name>* (and *emailed* when mail is set up).
- [ ] The test person's screens sign them out within a minute; Reports does too.
- [ ] The test person signs in: after the password, EA Explorer shows a **QR code**; scan it with the phone; type the
      code: they are in.
- [ ] A code from the **old phone** (or the old entry in the app) is refused at the next sign-in.
- [ ] The list now shows *set up* again; the audit trail has *security.mfa_reset* by the admin, *from users list*.
- [ ] Repeat with the multi-factor setting **off** and then **on for everyone** (System Admin › Security): it works
      the same.
- [ ] A User Admin asking it of a Super Admin is refused, saying why; so is an admin who ticks themselves.
- [ ] A token or API key of the test person still works after the reset.
