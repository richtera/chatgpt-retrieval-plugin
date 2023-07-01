# This is a version of the main.py file found in ../../../server/main.py without authentication.
# Copy and paste this into the main file at ../../../server/main.py if you choose to use no authentication for your retrieval plugin.
from typing import Optional
import uvicorn
import json
import yaml
# from pprint import pprint
from fastapi import FastAPI, File, Form, HTTPException, Body, UploadFile, Response
from fastapi.staticfiles import StaticFiles
from loguru import logger
from os import environ
from models.api import (
    DeleteRequest,
    DeleteResponse,
    QueryRequest,
    QueryResponse,
    UpsertRequest,
    UpsertResponse,
)
from datastore.factory import get_datastore
from services.file import get_document_from_file

from models.models import DocumentMetadata, Source


app = FastAPI()
with open("./.well-known/ai-plugin.json", "r") as f:
  plugin_json = json.load(f)
  plugin_json["api"]["url"] = (environ.get("HOST_URL") or "http://localhost:3333")+"/.well-known/openapi.yaml"
  plugin_json["logo_url"] = (environ.get("HOST_URL") or "http://localhost:3333")+"/.well-known/logo.png"

  plugin_json = json.dumps(plugin_json)

with open("./.well-known/openapi.yaml", "r") as f:
  plugin_yaml = yaml.load(f, Loader=yaml.FullLoader)
  plugin_yaml["info"]["servers"][0]["url"] = (environ.get("HOST_URL") or "http://localhost:3333")
  
  plugin_yaml = yaml.dump(plugin_yaml)
  
@app.route("/.well-known/ai-plugin.json")
def get_manifest(request):
    return Response(content=plugin_json, media_type="application/json")

@app.route("/.well-known/openapi.yaml")
def get_manifest(request):
    return Response(content=plugin_yaml, media_type="text/plain")

app.mount("/.well-known", StaticFiles(directory=".well-known"), name="static")

# Create a sub-application, in order to access just the query endpoints in the OpenAPI schema, found at http://0.0.0.0:8000/sub/openapi.json when the app is running locally
sub_app = FastAPI(
    title="Retrieval Plugin API",
    description="A retrieval API for querying and filtering documents based on natural language queries and metadata",
    version="1.0.0",
    servers=[{"url": environ.get("HOST_URL") or "http://localhost:3333"}],
)
app.mount("/sub", sub_app)


@app.post(
    "/upsert-file",
    response_model=UpsertResponse,
)
async def upsert_file(
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
):
    try:
        metadata_obj = (
            DocumentMetadata.parse_raw(metadata)
            if metadata
            else DocumentMetadata(source=Source.file)
        )
    except:
        metadata_obj = DocumentMetadata(source=Source.file)

    document = await get_document_from_file(file, metadata_obj)

    try:
        ids = await datastore.upsert([document])
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail=f"str({e})")


@app.post(
    "/upsert",
    response_model=UpsertResponse,
)
async def upsert(
    request: UpsertRequest = Body(...),
):
    try:
        ids = await datastore.upsert(request.documents)
        return UpsertResponse(ids=ids)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.post(
    "/query",
    response_model=QueryResponse,
)
async def query_main(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@sub_app.post(
    "/query",
    response_model=QueryResponse,
    description="Accepts search query objects with query and optional filter. Break down complex questions into sub-questions. Refine results by criteria, e.g. time / source, don't do this often. Split queries if ResponseTooLargeError occurs.",
)
async def query(
    request: QueryRequest = Body(...),
):
    try:
        results = await datastore.query(
            request.queries,
        )
        return QueryResponse(results=results)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.delete(
    "/delete",
    response_model=DeleteResponse,
)
async def delete(
    request: DeleteRequest = Body(...),
):
    if not (request.ids or request.filter or request.delete_all):
        raise HTTPException(
            status_code=400,
            detail="One of ids, filter, or delete_all is required",
        )
    try:
        success = await datastore.delete(
            ids=request.ids,
            filter=request.filter,
            delete_all=request.delete_all,
        )
        return DeleteResponse(success=success)
    except Exception as e:
        logger.error(e)
        raise HTTPException(status_code=500, detail="Internal Service Error")


@app.on_event("startup")
async def startup():
    global datastore
    datastore = await get_datastore()


def start():
    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)
