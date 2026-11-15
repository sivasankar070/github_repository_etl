FROM astrocrpublic.azurecr.io/runtime:3.3-11

# Copy the existing ETL source package into the Astro image
COPY src/ /usr/local/airflow/src/

# Make the project root available for Python imports
ENV PYTHONPATH="/usr/local/airflow:${PYTHONPATH}"