# EA Explorer web image (ours): React build served by unprivileged nginx on port 8080
FROM node:22-alpine AS build
WORKDIR /src
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
RUN npm run build

# the current stable line: 1.27 no longer gets fixes (R3.12)
FROM nginxinc/nginx-unprivileged:1.30-alpine
# the Alpine packages' own fixes (OpenSSL, brotli: R2.24), then back to the image's unprivileged user. Alpine's package
# index is fetched first so a new fix in it starts this step again: with the base image unchanged, Docker had kept the
# step from an older build and libxml2's fix of 20 Nov 2026 never came in (the full test of 24 Nov 2026, D912).
USER root
ADD https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/APKINDEX.tar.gz /tmp/apk-index.tar.gz
# nginx from Alpine's own packages (1.30.7, built 18 Nov 2026): the image's makers have not yet published one with the
# fixes of 1.30.7; the configuration uses only nginx's core (D912). The makers' optional modules (geoip, image-filter,
# njs, xslt) are taken out first: each is tied to their 1.30.6 and none is loaded here (the build of 24 Nov 2026, 19:52,
# "unable to select packages ... breaks: nginx-module-..."). nginx -t then checks the image's own configuration; it runs
# as root and leaves /tmp/nginx.pid and its temp folders as root's, so /tmp is emptied after it: the container runs as
# user 101 and stopped at start on "open() /tmp/nginx.pid failed (13: Permission denied)" (24 Nov 2026, 20:24).
RUN apk upgrade --no-cache \
 && apk info -q | grep '^nginx-module-' | xargs -r apk del --no-cache \
 && apk add --no-cache "nginx>=1.30.7" \
 && nginx -v && nginx -t \
 && rm -rf /tmp/* /tmp/.[!.]*
USER 101
ENV NGINX_ENVSUBST_FILTER="^EAX_"
COPY nginx/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /src/dist /usr/share/nginx/html
# the npm packages the screens were built from (not served): image scans (Trivy, phase 36.1) read them here
COPY --from=build /src/package.json /src/package-lock.json /usr/share/eax-web-build/
EXPOSE 8080
