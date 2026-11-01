**Docker walkthrough for this backend**

The Dockerfile lives at the repository root, beside `requirements.txt`. Build from that directory. The Python version matches the existing Python 3.12 development environment. This is a single-stage build: there is no compiled application artifact that needs a separate builder stage.

The accompanying changes add Gunicorn to `requirements.txt` and a `.dockerignore` file. Django application behavior and settings are unchanged. Preparing this image does not deploy it to Railway.

**The three objects you need to distinguish**

| Object | Meaning in this project |
| --- | --- |
| Dockerfile | Instructions describing how to package the backend. |
| Image | The resulting filesystem layers and configuration: Linux user-space files, Python, dependencies, application code, and startup defaults. |
| Container | An instance created from the image, with its own writable filesystem layer, environment, networking, and process configuration. It can be running or stopped. |

An image does not contain a running Django server. Starting a container launches the server. Linux containers share the host's Linux kernel; a Linux image does not carry a separate running kernel. Docker Desktop supplies a Linux VM when necessary.

** Every Dockerfile instruction, in order **l;;lo
\;'''';;;;;;;


Blank lines separate related instructions for readability; they do nothing during the build.

1. `FROM python:3.12-slim`

   Start a build stage from the official Python image. `3.12` selects the Python minor version. `slim` selects a smaller Debian-based variant with fewer operating-system packages. Python and pip are already installed. Docker downloads the image if it is not available locally, and reuses its existing layers; `FROM` does not manufacture one new application layer. A base image can contain several layers.

   The tag can receive updates. Pinning Python's minor version and direct dependency versions does not make the build byte-for-byte reproducible: the base tag and unpinned transitive dependencies can change. A digest and a complete dependency lock can address that later.

2. `ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1`

   Set two environment defaults for later build commands and for containers created from the image. The first prevents Python from writing imported modules' `.pyc` cache files. The second sends Python's stdout and stderr without Python's normal output buffering, helping logs appear promptly. This updates image configuration; it does not add a filesystem layer containing files. These variables do not configure Django's `DEBUG` or its secret key.

3. `WORKDIR /app`

   Set `/app` as the working directory for subsequent instructions and the default container command. Docker creates it if needed. Unlike a shell `cd` inside a `RUN`, this setting persists for later instructions. It sets configuration and can create a filesystem change when the directory is new.

4. `COPY requirements.txt ./`

   Copy `requirements.txt` from the build context into `/app/requirements.txt`. The source is relative to the build context on your computer. The destination `./` is relative to `/app` inside the image. This adds a filesystem layer containing the copied file.

5. `RUN pip install --no-cache-dir -r requirements.txt`

   Execute pip during the build, installing Django, DRF, Gunicorn, and the other requirements into this image's Python environment. `-r` reads the dependency list; `--no-cache-dir` avoids retaining pip's download cache. Installed packages and their command-line executables become filesystem changes in one layer. The temporary pip process ends when installation finishes.

   Docker's build cache and pip's download cache are different. Disabling pip's cache does not disable reuse of a previously built Docker layer. There is no need to copy your host `.venv`: the image has its own Python installation. The current dependencies have suitable binary distributions for this build, so no compiler installation is included.

6. `RUN useradd --create-home app && chown app:app /app`

   Create a Linux user named `app` and its home directory. `chown app:app /app` makes that user and group own the application directory. The `&&` runs the second command only if the first succeeds. Both commands belong to one `RUN`, so their filesystem changes are captured together in one layer. Changes include account records, the home directory, and ownership metadata. Owning `/app` also allows this project's local SQLite fallback to create a database there.

7. `COPY --chown=app:app core/ ./`

   Copy the contents of the repository's outer `core/` directory into `/app`, with ownership assigned to `app`. This creates a source-code filesystem layer. The resulting paths include `/app/manage.py`, `/app/core/settings.py`, and `/app/core/wsgi.py`. The outer directory is not copied as an extra `/app/core/manage.py` nesting level. Files excluded by `.dockerignore` are omitted.

8. `USER app`

   Set the default user for later `RUN` instructions and for the container's startup process. Gunicorn therefore runs as `app` rather than root. This is configuration, not a new filesystem layer. It does not change existing file ownership; the earlier commands did that.

9. `EXPOSE 8000`

   Document the default TCP port used by this application. This is configuration. It does not start a server, publish a host port, or force Railway to use port 8000. Publishing a local port is handled by `docker run -p`; the actual server port comes from the startup command.

10. `CMD ["sh", "-c", "exec gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 1 --access-logfile - --error-logfile -"]`

    Store the default container command. This instruction does not run Gunicorn during the build and does not create a filesystem layer.

    | Part | Purpose |
    | --- | --- |
    | JSON array | Specifies the executable and its arguments explicitly. |
    | `sh`, `-c` | Starts a shell to interpret the following command string. |
    | `${PORT:-8000}` | The shell uses a nonempty runtime `PORT`, otherwise 8000. Railway can supply `PORT` when starting the service. |
    | `exec` | Replaces the shell with Gunicorn, allowing Gunicorn to receive the container's stop signal directly as PID 1. |
    | `gunicorn` | Runs a WSGI HTTP server suitable for serving Django. |
    | `core.wsgi:application` | Imports `application` from `/app/core/wsgi.py`, which loads this Django project. |
    | `--bind 0.0.0.0:...` | Listens on all container network interfaces, allowing incoming connections through Docker or Railway networking. |
    | `--workers 1` | Starts one application worker, alongside Gunicorn's master process. This is a modest memory starting point; capacity still needs measurement. |
    | `--access-logfile -` | Sends HTTP access logs to stdout. |
    | `--error-logfile -` | Sends server error logs to stderr. |

    JSON exec form alone does not expand `$PORT`. Here it works because we explicitly invoke `sh -c`. You can override this entire default command at runtime, for example to run `python manage.py check`.

**Which instructions create layers?**

A filesystem layer stores a difference from the previous state: added files, changed files or metadata, and deletion markers. `COPY` and `RUN` create filesystem changes in this Dockerfile. `ENV`, `USER`, `EXPOSE`, and `CMD` store configuration. `WORKDIR` also creates a directory if needed. Build history can show configuration-only instructions as zero-size entries; a history entry is not necessarily an additional filesystem layer.

The conceptual stack is:

```text
Container writable layer               created when a container is created
-----------------------------------------------------------------------
Application source                     COPY core/ ./
User records and ownership changes      RUN useradd ... && chown ...
Installed Python dependencies           RUN pip install ...
Dependency list                         COPY requirements.txt ./
Application directory, if newly created WORKDIR /app
Existing Python + Debian base layers    FROM python:3.12-slim
```

Image configuration stores the environment, user, working directory, exposed port, and default command alongside the layer references. The image manifest identifies the configuration and its ordered layers. Layers are identified by content digests and can be shared between images.

At runtime, Docker presents the layers as one filesystem using its storage driver or snapshotter. They do not become one giant editable directory. Where an upper layer changes a lower layer's path, the upper view wins. Removing a lower-layer file hides it using deletion metadata; it does not erase the bytes from the lower image layer.

Each container gets its own writable layer. Modifying an image file uses copy-on-write behavior; the original image stays unchanged. Removing a container removes this writable state. Persistent databases and uploads therefore need external storage or volumes.

**Why requirements come before application code**

Docker can reuse unchanged build steps. When you edit only `core/catalog/views.py`, the requirements copy and pip installation can stay cached; the source copy and later dependent steps are processed again. Editing `requirements.txt` invalidates its copy and the dependency installation, along with later dependent steps. Copying all source before pip installation would make ordinary source changes unnecessarily invalidate that expensive installation step.

**What `.dockerignore` does**

Docker filters the build context using `.dockerignore`. Our file excludes Git metadata, your local virtual environment, browser artifacts, Python caches, `.env` files, local SQLite databases, uploads, and collected static files. `**` matches across directory levels; `*.py[cod]` matches Python cache-related extensions. `.gitignore` does not substitute for `.dockerignore`.

The Dockerfile copies only `requirements.txt` and `core/`. Local secrets and data should stay outside every image layer. Deleting a secret in a later `RUN` would still leave it recoverable from an earlier layer. Supply runtime secrets through Railway Variables or a local `--env-file` instead. Docker's env-file format expects `KEY=value`; a shell script or arbitrary dotenv syntax may need adjustment.

**Build the image locally**

Run from the repository root:

```bash
docker build -t ecommerce-backend:learning .
docker image ls ecommerce-backend
docker image history --no-trunc ecommerce-backend:learning
docker image inspect ecommerce-backend:learning --format '{{json .RootFS.Layers}}'
```

`docker build` reads the Dockerfile and creates or reuses the build results. `-t` gives the resulting image a name and tag. The final `.` selects the current directory as the build context, which determines what `COPY` can read. A tag is a human-readable reference, not a container and not the image's immutable identity.

`history` displays build history, including zero-size configuration entries. `inspect` displays the image's filesystem layer digest list. Building installs packages and copies files; it does not leave the web server running.

**Create a container and then start it**

```bash
docker create --name ecommerce-learning -p 127.0.0.1:8000:8000 ecommerce-backend:learning
docker start ecommerce-learning
docker logs ecommerce-learning
```

`create` prepares a stopped container with its own writable layer and port configuration. `start` launches its configured command. `-p 127.0.0.1:8000:8000` maps port 8000 on your computer's loopback interface to port 8000 inside the container. Open `http://localhost:8000/api/auth/me/`; an unauthenticated API response confirms that the HTTP server and Django routing are responding. The local database has no application tables yet, so endpoints that query them need migrations first.

`docker run` combines creation and startup:

```bash
docker run --rm --name ecommerce-run -p 127.0.0.1:8000:8000 ecommerce-backend:learning
```

This runs in the foreground. Stop it with Ctrl+C. `--rm` removes that container after it exits; the image remains. Add `-d` to run detached instead. Your previously created `ecommerce-learning` container must be stopped before another container can publish the same host port.

Inspect the running container and run management commands:

```bash
docker exec ecommerce-learning id
docker exec ecommerce-learning python manage.py check
docker exec ecommerce-learning python manage.py migrate
docker stop ecommerce-learning
docker rm ecommerce-learning
```

The migrate example creates tables in this disposable local container's SQLite database. These tables disappear when that container is removed. `docker stop` stops processes but retains the container and its writable state; `docker rm` removes it. `docker exec` starts another process inside an already running container.

To run an isolated command instead of the default Gunicorn server:

```bash
docker run --rm ecommerce-backend:learning python manage.py check
docker run --rm ecommerce-backend:learning python manage.py test
```

The arguments after the image name replace `CMD`. These commands do not read your host `.env`, and this project's test settings select an in-memory SQLite database.

To demonstrate a different runtime port:

```bash
docker run --rm -e PORT=9000 -p 127.0.0.1:8001:9000 ecommerce-backend:learning
```

Gunicorn now listens on container port 9000. Open `http://localhost:8001/api/auth/me/`. `EXPOSE 8000` does not prevent this.

**How this maps to Railway**

Use the repository root as Railway's service root so both the Dockerfile and `requirements.txt` are available. Railway detects a file named `Dockerfile` there and builds the image. Leave the service Start Command unset to use this image's `CMD`. Railway supplies runtime variables and starts the service from the image. Its public networking routes requests to the listening port; a local Docker `-p` mapping is not part of the Railway deployment.

Set your database and Cloudinary credentials through Railway Variables. The current settings read `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, and `DB_PORT`; they do not parse `DATABASE_URL`. Use the Railway Postgres private hostname for connections from this backend. Supply Cloudinary configuration using either `CLOUDINARY_URL` or the three existing `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` variables.

Migrations belong to deployment runtime operations, such as Railway's Pre-deploy Command `python manage.py migrate`, after the database variables are configured. Do not put database migrations in `RUN`: building an image should not modify a production database.

This Dockerfile packages the backend, but these existing Django settings need attention before public deployment:

- Read the production secret key from an environment variable; the checked-in key should be replaced.
- Read `DEBUG` and allowed hosts from configuration, disable debug in production, and allow the actual Railway or custom hostname. Adding variables alone does not work until settings.py reads them.
- Configure static-file collection and serving for the Django admin and DRF browsable API if you need them. Gunicorn by itself does not serve collected static files.
- Use Postgres for durable application data. Keep uploads in Cloudinary or durable storage; container-local SQLite and media do not survive container replacement.

The Dockerfile contains one Gunicorn worker to start with a modest memory footprint. Gunicorn still runs a master and worker, and Django's dependencies consume RAM even without traffic. An image's disk size and its running container's RAM consumption are different measurements.

**Explain it to your senior engineer**

“The Dockerfile starts from Python 3.12, sets Python logging defaults, installs dependencies in a reusable build layer, creates an unprivileged user, and copies our Django source. The image records how to launch Gunicorn, but the server starts only when a container starts. The container combines the image's immutable filesystem layers with its own writable layer. Gunicorn reads Railway's runtime port and imports our WSGI application. Secrets and persistent data stay outside the image.”

**Verification performed on this checkout**

- Built `ecommerce-backend:learning` successfully and rebuilt it with unchanged inputs; Docker reused the cached steps.
- Inspected the result: ten Dockerfile instructions, nine filesystem layers including the base image layers, default user `app`, and working directory `/app`.
- Confirmed that application source is present and `.env` files, SQLite files, Python caches, and the local media directory are absent from `/app` in the image.
- Ran Django's system check and all 13 existing tests successfully inside the image.
- Started disposable containers on port 8000 and with `PORT=9000`; both returned the expected HTTP 403 authentication response from `/api/auth/me/`.
- Applied migrations successfully to a disposable container's SQLite database as the non-root user. Removed the temporary verification containers afterward. The locally built image remains available.

**References**

- [Dockerfile reference](https://docs.docker.com/reference/dockerfile/)
- [Docker image layers](https://docs.docker.com/get-started/docker-concepts/building-images/understanding-image-layers/)
- [Docker build cache](https://docs.docker.com/build/cache/)
- [Running Docker containers](https://docs.docker.com/engine/containers/run/)
- [Railway Dockerfile builds](https://docs.railway.com/builds/dockerfiles)
- [Railway start commands](https://docs.railway.com/deployments/start-command)
