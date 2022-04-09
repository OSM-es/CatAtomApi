ARG FLASK_ENV=production
ARG FLASK_APP=api/api.py
ARG FLASK_PORT=5000
ARG user=catastro
ARG group=catastro

FROM catatom2osm AS base

LABEL maintainer="javiersanp@gmail.com"

ARG FLASK_ENV
ARG REQUISITES=requisites/$FLASK_ENV.txt

ENV APP_PATH=/opt/CatAtomAPI
ENV PYTHONPATH=$PYTHONPATH:$APP_PATH

USER root

WORKDIR $APP_PATH
COPY requisites/ requisites/
RUN pip install -r requisites/base.txt && \
    pip install -r $REQUISITES

FROM base AS production_stage
ONBUILD COPY . .

FROM base AS development_stage
ONBUILD RUN echo "Skip copy"

FROM ${FLASK_ENV}_stage AS final
ARG user
ARG group
ARG home
ARG FLASK_PORT
ARG FLASK_APP
ENV FLASK_APP=$FLASK_APP
ENV FLASK_PORT=$FLASK_PORT

RUN chown -R $user:$group $APP_PATH && \
    chown -R www-data:www-data /catastro && \
    usermod -a -G www-data $user

EXPOSE $FLASK_PORT

USER $user

CMD flask run --host 0.0.0.0 --port $FLASK_PORT
