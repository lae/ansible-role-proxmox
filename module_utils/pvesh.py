#!/usr/bin/python

import subprocess
import json
import re

from ansible.module_utils._text import to_text

class ProxmoxShellError(Exception):
    """Exception raised when an unexpected response code is thrown from pvesh."""
    def __init__(self, response):
        self.status_code = response["status"]
        self.message = response["message"]

        if "data" in response:
            self.data = response["data"]

def run_command(handler, resource, **params):
    # pvesh strips these before handling, so might as well
    resource = resource.strip('/')
    # pvesh only has lowercase handlers
    handler = handler.lower()
    command = [
        "/usr/bin/pvesh",
        handler,
        resource,
        "--output=json"]
    for parameter, value in params.items():
        command += ["-{}".format(parameter), "{}".format(value)]

    pipe = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (result, stderr) = pipe.communicate()
    result = to_text(result)
    stderr = to_text(stderr).splitlines()

    if len(stderr) == 0:
        if not result:
            return {u"status": 200}

        # Attempt to marshall the data into JSON
        try:
            data = json.loads(result)
        except ValueError:
            return {u"status": 200, u"data": result}

        # Otherwise return data as a string
        return {u"status": 200, u"data": data}

    if len(stderr) >= 1:
        # This will occur when a param's value is invalid
        if stderr[0] == "400 Parameter verification failed.":
            return {u"status": 400, u"message": "\n".join(stderr[1:-1])}

        if stderr[0] == "no '{}' handler for '{}'".format(handler, resource):
            return {u"status": 405, u"message": stderr[0]}

        if handler == "get":
            if any(re.match(pattern, stderr[0]) for pattern in [
                "^no such user \('.{3,64}?'\)$",
                "^(group|role|pool) '[A-Za-z0-9\.\-_]+' does not exist$",
                "^domain '[A-Za-z][A-Za-z0-9\.\-_]+' does not exist$"]):
                return {u"status": 404, u"message": stderr[0]}

        # This will occur when a param is invalid
        if len(stderr) >=2 and stderr[-2].startswith("400 unable to parse"):
            return {u"status": 400, u"message": "\n".join(stderr[:-1])}

        return {u"status": 500, u"message": u"\n".join(stderr), u"data": result}

    return {u"status": 500, u"message": u"Unexpected result occurred but no error message was provided by pvesh."}

def get(resource):
    response = run_command("get", resource)

    if response["status"] == 404:
        return None

    if response["status"] == 200:
        return response["data"]

    raise ProxmoxShellError(response)

def delete(resource):
    response = run_command("delete", resource)

    if response["status"] != 200:
        raise ProxmoxShellError(response)

def create(resource, **params):
    response = run_command("create", resource, **params)

    if response["status"] != 200:
        raise ProxmoxShellError(response)

def set(resource, **params):
    response = run_command("set", resource, **params)

    if response["status"] != 200:
        raise ProxmoxShellError(response)
