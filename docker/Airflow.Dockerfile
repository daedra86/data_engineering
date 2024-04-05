ARG BASE_AIRFLOW_IMAGE

FROM ${BASE_AIRFLOW_IMAGE} as air

ENV AIRFLOW_HOME=/opt/airflow

USER root
RUN apt-get update && apt-get install -y python3-pip

USER $AIRFLOW_UID

COPY requirements.txt .
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --no-cache-dir -r requirements.txt

USER root

COPY scripts scripts
RUN chmod +x scripts
