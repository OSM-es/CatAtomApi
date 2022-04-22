ARG FLASK_ENV=production
ARG FLASK_APP=api.py
ARG FLASK_PORT=5000
ARG RELOAD=""
ARG user=catastro
ARG group=catastro

FROM catatom2osm AS base

LABEL maintainer="javiersanp@gmail.com"

ARG FLASK_ENV

ENV APP_PATH=/opt/CatAtomAPI
ENV PYTHONPATH=$PYTHONPATH:$APP_PATH
ENV QT_QPA_PLATFORM=offscreen

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
ARG home
ARG FLASK_PORT
ARG FLASK_APP
ARG RELOAD
ENV FLASK_APP=$FLASK_APP
ENV FLASK_PORT=$FLASK_PORT
ENV RELOAD=$RELOAD

RUN chown -R $user:$group $APP_PATH && \
    chown -R www-data:www-data /catastro && \
    usermod -a -G www-data $user

EXPOSE $FLASK_PORT

USER $user

CMD gunicorn --bind 0.0.0.0:$FLASK_PORT --workers 4 api:app $RELOAD

