# The images EA Explorer publishes (Release 14.8.1, D973; eax, D976): built by `docker buildx bake` from the published workflow
# (.github/workflows/publish-images.yml) when a release is tagged, for Intel/AMD and ARM, and pushed to Docker Hub and
# GitHub's registry. Only our own images are here; PostgreSQL, Valkey, nginx, Keycloak, Mayan, k6 and SonarQube are used
# as their makers publish them (docs/images.md says which version of each, and what we change in ours).
#
# api, library and testrunner are published with what an installation would otherwise read from this repository's
# folders (the docs, the help, the release notes, the templates, the test data; docker-compose.yml mounts them on a
# developer's machine): their base is built from the service's own Dockerfile, then deploy/release/<image>.Dockerfile
# adds those files, its <image>.Dockerfile.dockerignore letting only them in. A local build (eax up) is unchanged.
#
#   docker buildx bake -f deploy/release/docker-bake.hcl                     # build every image here (no push)
#   VERSION=14.8.0 MINOR=14.8 docker buildx bake -f deploy/release/docker-bake.hcl --push

variable "VERSION" { default = "dev" }
variable "MINOR" { default = "" }                 # 14.8 for 14.8.0: a tag that follows the newest patch
variable "LATEST" { default = "false" }           # "true": also tag latest (a release, not a test build)
variable "HUB" { default = "eaexplorer/" }        # Docker Hub: <HUB><image>, e.g. eaexplorer/api or gauravvermaea/eaexplorer-api
variable "GHCR" { default = "" }                  # GitHub's registry, e.g. ghcr.io/gauravvermaea/eaexplorer- ("" leaves it out)
variable "PLATFORMS" { default = "linux/amd64,linux/arm64" }

function "tags" {
  params = [name]
  result = flatten([
    for prefix in compact([HUB, GHCR]) : compact([
      "${prefix}${name}:${VERSION}",
      MINOR != "" ? "${prefix}${name}:${MINOR}" : "",
      LATEST == "true" ? "${prefix}${name}:latest" : "",
    ])
  ])
}

group "default" {
  targets = ["api", "web", "backup", "library", "views", "ops", "drawio", "superset", "jenkins", "testrunner", "eax"]
}

target "_common" {
  platforms = split(",", PLATFORMS)
  labels = {
    "org.opencontainers.image.version"  = VERSION
    "org.opencontainers.image.licenses" = "AGPL-3.0-only"
    "org.opencontainers.image.source"   = "https://github.com/gauravvermaea/EA-Explorer"
    "org.opencontainers.image.documentation" = "https://github.com/gauravvermaea/EA-Explorer/blob/main/docs/images.md"
  }
}

# ---------------------------------------------------------------- the bases (not pushed)
target "api-base" {
  inherits = ["_common"]
  context  = "services/api"
}
target "library-base" {
  inherits = ["_common"]
  context  = "services/library"
}
target "testrunner-base" {
  inherits   = ["_common"]
  context    = "services/api"
  dockerfile = "Dockerfile.test"
}

# ---------------------------------------------------------------- what is published
target "api" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "deploy/release/api.Dockerfile"
  contexts   = { base = "target:api-base" }
  tags       = tags("api")
}
target "library" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "deploy/release/library.Dockerfile"
  contexts   = { base = "target:library-base" }
  tags       = tags("library")
}
target "testrunner" {
  inherits   = ["_common"]
  context    = "."
  dockerfile = "deploy/release/testrunner.Dockerfile"
  contexts   = { base = "target:testrunner-base" }
  tags       = tags("testrunner")
}
target "web" {
  inherits = ["_common"]
  context  = "services/web"
  tags     = tags("web")
}
target "backup" {
  inherits = ["_common"]
  context  = "services/backup"
  tags     = tags("backup")
}
target "views" {
  inherits = ["_common"]
  context  = "services/views"
  tags     = tags("views")
}
target "ops" {
  inherits = ["_common"]
  context  = "services/ops"
  tags     = tags("ops")
}
target "drawio" {
  inherits = ["_common"]
  context  = "deploy/drawio"
  tags     = tags("drawio")
}
target "superset" {
  inherits = ["_common"]
  context  = "deploy/superset"
  tags     = tags("superset")
}
target "jenkins" {
  inherits = ["_common"]
  context  = "deploy/jenkins"
  tags     = tags("jenkins")
}
# eax itself in a container (D976): a machine needs only Docker
target "eax" {
  inherits = ["_common"]
  context  = "deploy/eax"
  tags     = tags("eax")
}
