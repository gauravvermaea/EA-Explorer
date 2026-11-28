# The published test runner (D973): services/api/Dockerfile.test's image, plus the test data (testbench/data: deliveries,
# workbooks, uploads, expected results; mounted at /testdata on a developer's machine), so an installation made from the
# deploy repository alone can run eax test smoke and eax test full.
FROM base
USER root
COPY testbench/data /testdata
USER eax
