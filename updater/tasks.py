#!/usr/bin/env python
from invoke import task
import yaml
import json
import csv
import sys
import ctypes
from solr import SolrClient
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

@task
def update_schema(c, schema, core, server=DEFAULT_SOLR_URL):
    """
    Updates schema.
    """
    client = SolrClient(core=core, base_url=server)
    parsed_schema = _load_yaml(path=schema)
    client.update_field_types(parsed_schema["types"], core=core, server=server)
    client.update_fields(parsed_schema["fields"], core=core, server=server)

@task
def delete_index(c, core, server=DEFAULT_SOLR_URL):
    """
    Delete index data.
    """
    client = SolrClient(core=core, base_url=server)
    client.delete_all_index()

@task
def index(c, data, core, server=DEFAULT_SOLR_URL):
    """
    Update data.
    """
    client = SolrClient(core=core, base_url=server)
    with open(data) as csvfile:
        # Polygon filed string is too long from default csv.field_size_limit (= 131072)
        csv.field_size_limit(sys.maxsize)
        reader = csv.DictReader(csvfile, delimiter='\t')
        client.index(documents=reader)
    client.commit(core=core, server=server)
