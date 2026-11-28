# test-runner

The self-test's runner (about 1.5 GB), started for a test and removed after it.

**The settings** (work/eaexplorer.env): ./eax.sh test smoke|full starts it as a test needs; by hand only to look inside it.

## Once, with eax

The settings file and the files the services read their passwords from are made by eax, so start with it once
(from the repository's top folder):

```bash
./eax.sh init laptop          # the settings, every password strong and random
./eax.sh images pull --with-tests          # this release's images, named as the compose file knows them
```

## Then with plain Docker Compose

From the repository's top folder:

```bash
docker compose --env-file work/eaexplorer.env -f docker-compose.yml -f deploy/compose/docker-compose.<laptop|server>.yml --profile test run --rm testrunner bash
```

Stop: the same with `down` (the data is kept). The same files are what `./eax.sh up` uses for this case, so you can
switch between eax and plain compose. What each image is: [guides/images.md](../../guides/images.md).
