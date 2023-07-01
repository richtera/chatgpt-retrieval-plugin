#!/usr/bin/env bash

. ./env.sh

IMAGE=$(docker build -q .)
docker run -it \
  -e DATASTORE \
  -e BEARER_TOKEN \
  -e OPENAI_API_KEY \
  -e WEAVIATE_URL \
  -e WEAVIATE_API_KEY \
  -e WEAVIATE_CLASS=Document \
  $IMAGE
