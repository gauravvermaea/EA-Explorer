# For an AI or a person working on this repository

This is **EA Explorer's deploy repository**: only how to run EA Explorer. **Nothing here is written by hand.** Every
file listed in MANIFEST.txt is made by `tools/deploy_repo.py` in the code repository ({{CODE_REPO}}, the folder
`EA-Enterpise` on the owner's laptop) from its release; change it there and run the tool again. Only `.git` and
`LICENSE` are this repository's own.

- The code, the images and their Dockerfiles, the tests and the decisions (docs/decisions.md, D973 onwards) are in the
  code repository.
- The images are published from the code repository (`.github/workflows/publish-images.yml`) to GitHub's registry
  ({{REGISTRY}}<image>), and later Docker Hub.
- Never write code changes here; never write deploy files into the code repository except through `deploy/repo/` there.
