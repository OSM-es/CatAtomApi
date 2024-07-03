ARG FLASK_ENV=production
ARG FLASK_APP=api.py
ARG FLASK_PORT=5000
ARG RELOAD=""
ARG user=www-data
ARG group=www-data

FROM catatom2osm4api AS base

LABEL maintainer="javiersanp@gmail.com"

ARG FLASK_ENV
ARG user

ENV APP_PATH=/opt/CatAtomAPI
ENV PYTHONPATH=$PYTHONPATH:$APP_PATH
ENV QT_QPA_PLATFORM=offscreen
ENV XDG_RUNTIME_DIR="/tmp/runtime-$user"
ENV PYTHONUNBUFFERED=1

USER root

WORKDIR $APP_PATH
COPY requisites.txt .
RUN pip install -r requisites.txt

FROM base AS production_stage
ONBUILD COPY . .

FROM base AS development_stage
ONBUILD RUN echo "Skip copy"

FROM ${FLASK_ENV}_stage AS final
ARG user
ARG group
ARG FLASK_PORT
ARG FLASK_APP
ARG RELOAD
ARG HOME=/catastro
ENV FLASK_APP=$FLASK_APP
ENV FLASK_PORT=$FLASK_PORT
ENV RELOAD=$RELOAD
ENV HOME=$HOME

RUN chown -R $user:$group $APP_PATH $XDG_RUNTIME_DIR

EXPOSE $FLASK_PORT

USER $user

CMD [ "python3", "-u", "./api.py" ]
