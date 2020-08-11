# Docker Instructions

Compiled versions of `hummingbot` are available on Docker Hub at [`theholiestroger/hummingbot`](https://hub.docker.com/r/theholiestroger/hummingbot).

## Running `hummingbot` with Docker

For instructions on operating `hummingbot` with Docker, navigate to [`hummingbot` documentation: Install with Docker](https://docs.hummingbot.io/installation/#install-via-docker).

---

## Development commands: deploying to Docker Hub

### Create docker image

```sh
# Create a label for image
export TAG=my-label

# Build docker image
$ docker build -t theholiestroger/hummingbot:$TAG -f Dockerfile .

# Push docker image to docker hub
$ docker push theholiestroger/hummingbot:$TAG
```

#### Build and Push

```sh
$ docker image rm theholiestroger/hummingbot:$TAG && \
  docker build -t theholiestroger/hummingbot:$TAG -f Dockerfile . && \
  docker push theholiestroger/hummingbot:$TAG
```
