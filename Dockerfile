ARG APP_ENV=prod
ARG user=catastro
ARG group=catastro
ARG home=/catastro

FROM catatom2osm AS base

LABEL maintainer="javiersanp@gmail.com"

ARG APP_ENV
ARG REQUISITES=requisites-$APP_ENV.txt
ARG user
ARG group
ARG home

ENV APP_PATH=/opt/CatAtomAPI
ENV PYTHONPATH=$PYTHONPATH:$APP_PATH

USER root

WORKDIR $APP_PATH
COPY $REQUISITES ./
RUN pip install -r $REQUISITES

FROM base AS prod_stage
ONBUILD COPY . .

FROM base AS dev_stage
ONBUILD RUN echo "Skip copy"

FROM ${APP_ENV}_stage AS final
ARG user
ARG group
ARG home

RUN chown -R $user:$group $APP_PATH

USER $user
WORKDIR $home
