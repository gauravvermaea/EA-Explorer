# server

A server for a team: HTTPS with your certificate, strong passwords, no sample data.

**The settings** (work/eaexplorer.env): EAX_DEPLOYMENT=server, EAX_HOSTNAME.

## Once, with eax

The settings file and the files the services read their passwords from are made by eax, so start with it once
(from the repository's top folder):

```bash
./eax.sh init server          # the settings, every password strong and random
./eax.sh images pull          # this release's images, named as the compose file knows them
```

## Then with plain Docker Compose

From the repository's top folder:

```bash
docker compose --env-file work/eaexplorer.env -f docker-compose.yml -f deploy/compose/docker-compose.server.yml up -d
```

Stop: the same with `down` (the data is kept). The same files are what `./eax.sh up` uses for this case, so you can
switch between eax and plain compose. What each image is: [guides/images.md](../../guides/images.md).
