#!/usr/bin/env python
from invoke import task
import yaml
import json
import csv
import sys
import ctypes
from urllib.request import Request, urlopen, HTTPError, URLError
from typing import Dict, Iterator

DEFAULT_SOLR_URL = 'http://localhost:8983/solr'
# max_long. cf: https://docs.python.org/3/library/ctypes.html#module-ctypes
MAX_CSV_FIELD_SIZE = int(ctypes.c_ulong(-1).value // 2)

def _load_yaml(path: str):
    """
    Load yaml file from path.
    """
    with open(path) as file:
        return yaml.load(file, Loader=yaml.SafeLoader)

def _exists_field_type(field_type_name: str, core: str, server: str = DEFAULT_SOLR_URL) -> bool:
    url = f"{server}/{core}/schema/fieldtypes/{field_type_name}"
    req = Request(url)
    try:
        with urlopen(req) as _:
            return True
    except HTTPError as err:
        if err.code == 404:
            return False
        raise err

def _update_field_type(field_type: Dict, core: str, server: str = DEFAULT_SOLR_URL):
    url = f"{server}/{core}/schema"
    if _exists_field_type(field_type_name=field_type['name'], core=core, server=server):
        data = {"replace-field-type": field_type}
    else:
        data = {"add-field-type": field_type}
    headers = {"Content-type": "application/json"}
    req = Request(url, json.dumps(data).encode(), headers, method='POST')
    try:
        with urlopen(req) as res:
            _ = res.read()
    except HTTPError as err:
        print(err.code)
        print(err.reason)
        raise err
    except URLError as err:
        print(err.reason)
        raise err

def _update_field_types(field_types: Iterator, core: str, server: str = DEFAULT_SOLR_URL):
    for field_type in field_types:
        _update_field_type(field_type=field_type, core =core, server=server)

def _exists_field(field_name: str, core: str, server: str = DEFAULT_SOLR_URL) -> bool:
    url = f"{server}/{core}/schema/fields/{field_name}"
    req = Request(url)
    try:
        with urlopen(req) as _:
            return True
    except HTTPError as err:
        if err.code == 404:
            return False
        raise err
        
def _update_field(field: str, core: str, server: str = DEFAULT_SOLR_URL):
    """
    curl -X POST -H 'Content-type:application/json' --data-binary '{
        "add-field":{
            "name":"sell-by",
            "type":"tdate",
            "stored":true
        }
    }' ${field}/${core}/schema
    """
    if _exists_field(field_name=field['name'], core=core, server=server):
        data = {"replace-field": field}
    else:
        data = {"add-field": field}
    url = f"{server}/{core}/schema"
    headers = {"Content-type": "application/json"}
    req = Request(url, json.dumps(data).encode(), headers, method='POST')
    try:
        with urlopen(req) as res:
            _ = res.read()
    except HTTPError as err:
        print(err.code)
        print(err.reason)
        raise err
    except URLError as err:
        print(err.reason)
        raise err

def _update_fields(fields: str, core: str, server: str = DEFAULT_SOLR_URL):
    for field in fields:
        _update_field(field=field, server=server, core=core)

def _index_document(document: Dict, core: str, server: str = DEFAULT_SOLR_URL):
    url = f"{server}/{core}/update/json/docs"
    headers = {"Content-type": "application/json"}
    req = Request(url, json.dumps(document).encode(), headers, method="POST")
    try:
        with urlopen(req) as res:
            _ = res.read()
    except HTTPError as err:
        print(err.code)
        print(err.reason)
        if err.code == 400:
            print(f"[ERROR]: Skipped to index {document['ADMIN']}")
            return
        raise err
    except URLError as err:
        print(err.reason)
        raise err

def _commit(core: str, server: str = DEFAULT_SOLR_URL):
    url = f"{server}/{core}/update?commit=true"
    req = Request(url)
    try:
        with urlopen(req) as res:
            _ = res.read()
    except HTTPError as err:
        print(err.code)
        print(err.reason)
        raise err
    except URLError as err:
        print(err.reason)
        raise err

@task
def update_schema(c, schema, core, server=DEFAULT_SOLR_URL):
    """
    Updates schema.
    """
    parsed_schema = _load_yaml(path=schema)
    _update_field_types(parsed_schema["types"], core=core, server=server)
    _update_fields(parsed_schema["fields"], core=core, server=server)

@task
def delete_index(c, core, server=DEFAULT_SOLR_URL):
    """
    Delete index data.
    """
    data = {
        "delete": {
            "query": "*:*"
        }
    }
    url = f"{server}/{core}/update?commit=true"
    headers = {"Content-type": "application/json"}
    req = Request(url, json.dumps(data).encode(), headers)
    try:
        with urlopen(req) as res:
            _ = res.read()
    except HTTPError as err:
        print(err.code)
        print(err.reason)
        raise err
    except URLError as err:
        print(err.reason)
        raise err

@task
def index(c, data, core, server=DEFAULT_SOLR_URL):
    """
    Update data.
    """
    with open(data) as csvfile:
        # Polygon filed string is too long from default csv.field_size_limit (= 131072)
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(csvfile, delimiter='\t')
        for row in reader:
            _index_document(row, core=core, server=server)
    _commit(core=core, server=server)