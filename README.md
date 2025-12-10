# Python Automation Base Image

This repository bootstraps a personal GitLab project that builds a bespoke
Python base image (`repo.nonprod.pcfcloud.io/docker/build/python:3.11-base-latest`)
and bakes in a reusable DevOps automation script. Clone the repo into your
personal GitLab namespace, hook it up to CI/CD, and you'll get a ready-to-use
image you can reference from downstream services or jobs.

## What you get

- `Dockerfile` that extends the corporate Python base image and copies the
  automation scripts into `/opt/automation`.
- `scripts/devops_health_check.py`, an MIT-licensed script that inspects
  uptime, load average, disk utilisation, and failed systemd units to provide a
  lightweight health signal for any environment that can run Python.
- `.gitlab-ci.yml` that builds and pushes the derived image to your project’s
  Container Registry on every push.

## Local quickstart

```bash
# Build with Docker or podman
export IMAGE_NAME=python-automation-base:dev
podman build -t "$IMAGE_NAME" .

# Run the baked-in script (exit code 2 when any alert triggers)
podman run --rm "$IMAGE_NAME" --max-disk-percent 70
```

## Creating the GitLab project

1. In GitLab (`gitlab.lblw.ca`), create a **New project → Create blank project**
   under your personal namespace. Example name: `python-automation-base`.
2. Enable the Container Registry for the project (Project settings → Packages
   and registries → Container Registry).
3. Ensure your shared runner is allowed to run privileged builds (required for
   Docker-in-Docker). If not available, register a personal runner with the
   `--privileged` flag.
4. Add the following CI/CD variables under *Settings → CI/CD → Variables*:
   - `CI_REGISTRY_USER` and `CI_REGISTRY_PASSWORD`: typically set to the
     built-in `$CI_REGISTRY_USER`/`$CI_JOB_TOKEN` pair, but you can override
     with a robot account if preferred.
   - Optional `IMAGE_NAME` override if you do not want the default path of
     `$CI_REGISTRY_IMAGE/python-automation-base`.
5. Push this repository to the new GitLab project:

```bash
git remote add origin git@gitlab.lblw.ca:<your-namespace>/python-automation-base.git
git push -u origin main
```

Once pushed, the default pipeline defined in `.gitlab-ci.yml` will:

- Authenticate to the GitLab Container Registry.
- Build the Dockerfile, tagging the image with both `latest` and the short
  commit SHA.
- Push both tags so you have immutable references for releases.

## Using the automation script from other components

The baked image exposes the health-check script as its default entrypoint, so
any job or workload that runs the container will automatically emit the report
and fail fast (exit code 2) when disks or services are outside tolerance. You
can also shell into the container and reuse the script for ad-hoc diagnostics:

```bash
podman run -it --rm "$IMAGE_NAME" bash
python /opt/automation/devops_health_check.py --format text
```

Feel free to drop additional scripts into `scripts/` or extend the Dockerfile
with project-specific dependencies as your automation footprint grows.
