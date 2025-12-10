# syntax=docker/dockerfile:1.7
FROM repo.nonprod.pcfcloud.io/docker/build/python:3.11-base-latest

LABEL maintainer="pcf-engineering" \
      org.opencontainers.image.title="python-automation-base" \
      org.opencontainers.image.description="Python base image bundled with reusable DevOps automation scripts."

ENV AUTOMATION_HOME=/opt/automation \
    PYTHONUNBUFFERED=1

WORKDIR ${AUTOMATION_HOME}
COPY scripts/ ${AUTOMATION_HOME}/

# Validate that the script is executable at build time.
RUN chmod +x ${AUTOMATION_HOME}/devops_health_check.py && \
    ${AUTOMATION_HOME}/devops_health_check.py --format json --max-disk-percent 101 >/dev/null

ENTRYPOINT ["python", "/opt/automation/devops_health_check.py"]
