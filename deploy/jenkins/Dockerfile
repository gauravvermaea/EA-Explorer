# Jenkins for EA Explorer (Release 6.6, R6.6-J1, D748): the pipelines are made from the catalogue at start (Job DSL),
# the settings from casc.yaml (configuration as code); nothing is set up by hand. It runs no Docker: it calls the agent
# on the machine (eax jenkins agent) with a token.
# The newest long-term-support Jenkins: jenkins-plugin-cli installs each plugin's newest version, which needs a recent
# Jenkins (the owner's first `eax jenkins up`, 18 Nov 2026, 09:21: plugins.txt refused on 2.479.3). EAX_JENKINS_IMAGE
# pins another (e.g. jenkins/jenkins:2.516.3-lts-jdk21) when a site wants a fixed one.
ARG JENKINS_IMAGE=jenkins/jenkins:lts-jdk21
FROM ${JENKINS_IMAGE}
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false" \
    CASC_JENKINS_CONFIG=/usr/share/jenkins/ref/casc.yaml
COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN jenkins-plugin-cli --verbose --plugin-file /usr/share/jenkins/ref/plugins.txt
COPY casc.yaml casc-keycloak.yaml /usr/share/jenkins/ref/
COPY seed.groovy /usr/share/jenkins/ref/seed.groovy
