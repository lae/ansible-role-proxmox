#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "thystips",
}

DOCUMENTATION = """
---
module: proxmox_metric_server
short_description: Manages the Metric Server in Proxmox
options:
    id:
        required: true
        type: str
        description:
            - ID of the server.
    port:
        type: int
        default: 8089
        description:
            - Port of the server.
    server:
        required: true
        type: str
        description:
            - Server dns name or IP address.
    type:
        type: str
        default: "influxdb"
        choices: [ "influxdb", "graphite" ]
        description:
            - Plugin type.
    protocol:
        type: str
        default: "udp"
        choices: [ "udp", "tcp", "http", "https" ]
        description:
            - Protocol used to send metrics.
            - "http" and "https" are only available for "influxdb" type and using http v2 api.
            - "tcp" is only available for "graphite" type.
    disable:
        type: bool
        default: false
        description:
            - Disable the metric server.
    organization:
        type: str
        description:
            - Organization name.
            - Only available for "influxdb" with http v2 api.
    bucket:
        type: str
        description:
            - Bucket name for "influxdb" type.
            - Only useful with http v2 api or compatible.
    token:
        type: str
        description:
            - The InfluxDB access token.
            - Only necessary when using the http v2 api.
            - If the v2 compatibility api is used, use 'user:password' instead.
    path:
        type: str
        description:
            - Root Graphite path.
            - Only available for "graphite" type.
    api_path_prefix:
        type: str
        description:
            - An API path prefix inserted between '<host>:<port>/' and '/api2/'.
            - Can be useful if the InfluxDB service runs behind a reverse proxy.
            - Only available for "influxdb" with http v2 api.
    timeout:
        type: int
        description:
            - Timeout in seconds.
            - Only available for "influxdb" with http v2 api or Graphite TCP socket.
    max_body_size:
        type: bytes
        default: 25000000
        description:
            - Maximum body size in bytes.
            - Only available for "influxdb" with http v2 api.
    mtu:
        type: int
        description:
            - MTU for UDP metrics transmission.
    verify_certificate:
        type: bool
        description:
            - Verify the SSL certificate.
            - Only available for "influxdb" with https.
    state:
        type: str
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Whether the server should exist or not.

author:
    - ThysTips (@thystips)
"""

EXAMPLES = """
- name: Create a new InfluxDB metric server
  proxmox_metric_server:
    id: "influxdb"
    port: 8086
    server: "influxdb.example.com"
    type: "influxdb"
    protocol: "http"
    organization: "myorg"
    bucket: "mybucket"
    token: "mytoken"
"""

RETURN = """
"""

from ansible.module_utils.basic import AnsibleModule  # noqa: E402
from ansible.module_utils._text import to_text  # noqa: E402, F401
from ansible.module_utils.pvesh import ProxmoxShellError  # type: ignore # noqa: E402
import ansible.module_utils.pvesh as pvesh  # type: ignore # noqa: E402


class ProxmoxMetricServer(object):
    def __init__(self, module):
        self.module = module
        self.id = module.params["id"]
        self.port = module.params["port"]
        self.server = module.params["server"]
        self.type = module.params["type"]
        self.protocol = module.params["protocol"]
        self.disable = module.params["disable"]
        self.organization = module.params["organization"]
        self.bucket = module.params["bucket"]
        self.token = module.params["token"]
        self.path = module.params["path"]
        self.api_path_prefix = module.params["api_path_prefix"]
        self.timeout = module.params["timeout"]
        self.max_body_size = module.params["max_body_size"]
        self.mtu = module.params["mtu"]
        self.verify_certificate = module.params["verify_certificate"]
        self.state = module.params["state"]

        try:
            self.existing_servers = pvesh.get("cluster/metrics/server")
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

        self.parse_servers()

    def parse_servers(self):
        self.servers = []
        self.servers.extend(
            existing_servers.get("id")
            for existing_servers in self.existing_servers
        )

    def lookup(self):
        return next(
            (
                {"id": existing_servers.get("id")}
                for existing_servers in self.existing_servers
                if existing_servers.get("id") == self.id
            ),
            None,
        )

    def exists(self):
        return self.id in self.servers

    def prepare_server_args(self, create=True):
        args = {"port": self.port, "server": self.server}

        if create:
            args["type"] = self.type
        if self.protocol is not None:
            args["influxdbproto" if self.type == "influxdb" else "proto"] = self.protocol
        args["disable"] = int(self.disable)
        if self.organization is not None:
            args["organization"] = self.organization
        if self.bucket is not None:
            args["bucket"] = self.bucket
        if self.token is not None:
            args["token"] = self.token
        if self.path is not None:
            args["path"] = self.path
        if self.api_path_prefix is not None:
            args["api-path-prefix"] = self.api_path_prefix
        if self.timeout is not None:
            args["timeout"] = self.timeout
        if self.max_body_size is not None:
            args["max-body-size"] = self.max_body_size
        if self.mtu is not None:
            args["mtu"] = self.mtu
        if self.verify_certificate is not None:
            args["verify-certificate"] = int(self.verify_certificate)

        return args

    def remove_server(self):
        try:
            pvesh.delete(f"cluster/metrics/server/{self.id}")
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_server(self):
        new_server = self.prepare_server_args()

        try:
            pvesh.create(f"cluster/metrics/server/{self.id}", **new_server)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_server(self):
        existing_servers = self.lookup()
        modified_server = self.prepare_server_args(create=False)
        updated_fields = []
        error = None

        for key in modified_server:
            if key not in existing_servers:  # type: ignore
                updated_fields.append(key)
            else:
                new_value = modified_server.get(key)
                old_value = existing_servers.get(key)  # type: ignore
                if isinstance(old_value, list):
                    old_value = ",".join(sorted(old_value))
                if isinstance(new_value, list):
                    new_value = ",".join(sorted(new_value))

                if new_value != old_value:
                    updated_fields.append(key)

        if self.module.check_mode:
            self.module.exit_json(
                changed=bool(updated_fields), expected_changes=updated_fields
            )

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set(f"cluster/metrics/server/{self.id}", **modified_server)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)


def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html#/cluster/metrics/server/{id}
    module_args = dict(
        id=dict(type="str", required=True),
        port=dict(type="int", default=8089),
        type=dict(type="str", default="influxdb", choices=["influxdb", "graphite"]),
        server=dict(type="str", required=True),
        protocol=dict(
            type="str",
            default="udp",
            choices=["udp", "tcp", "http", "https"],
        ),
        disable=dict(type="bool", default=False),
        organization=dict(type="str"),
        bucket=dict(type="str"),
        token=dict(type="str"),
        path=dict(type="str"),
        api_path_prefix=dict(type="str"),
        timeout=dict(type="int"),
        max_body_size=dict(type="bytes"),
        mtu=dict(type="int"),
        verify_certificate=dict(type="bool"),
        state=dict(default="present", choices=["present", "absent"], type="str"),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ["protocol", "http", ["organization", "bucket", "token"]],
            ["protocol", "https", ["organization", "bucket", "token"]],
        ],
        mutually_exclusive=[
            ("organization", "mtu"),
            ("bucket", "mtu"),
            ("token", "mtu"),
            ("api_path_prefix", "mtu"),
            ("timeout", "mtu"),
            ("max_body_size", "mtu"),
            ("verify_certificate", "mtu"),
            ("organization", "path"),
            ("bucket", "path"),
            ("token", "path"),
            ("api_path_prefix", "path"),
            ("max_body_size", "path"),
            ("verify_certificate", "path"),
        ],
    )

    if (
        module.params["protocol"] in ["tcp", "http", "https"]
        and module.params["mtu"] is not None
    ):
        module.fail_json(
            msg="The 'mtu' parameter is only available for 'udp' protocol."
        )

    if module.params["type"] == "graphite" and module.params["protocol"] not in [
        "tcp",
        "udp",
    ]:
        module.fail_json(
            msg="The 'protocol' parameter must be 'tcp' or 'udp' for 'graphite' type."
        )

    if module.params["type"] == "influxdb" and module.params["protocol"] == "tcp":
        module.fail_json(
            msg="The 'protocol' parameter must be 'udp', 'http' or 'https' for 'influxdb' type."
        )

    if module.params["type"] == "influxdb" and module.params["path"] is not None:
        module.fail_json(
            msg="The 'path' parameter is only available for 'graphite' type."
        )

    if (
        module.params["protocol"] in ["http", "https"]
        and module.params["type"] == "graphite"
    ):
        module.fail_json(
            msg="The 'protocol' parameter must be 'tcp' or 'udp' for 'graphite' type."
        )

    if module.params["type"] == "graphite" and any(
        module.params.get(param) is not None
        for param in ["bucket", "organization", "token"]
    ):
        module.fail_json(
            msg="The 'bucket', 'organization' and 'token' parameters are only available for 'influxdb' type."
        )

    if module.params["protocol"] == "udp" and module.params["timeout"] is not None:
        module.fail_json(
            msg="The 'timeout' parameter is only available for 'influxdb' with http v2 api or Graphite TCP socket."
        )

    if module.params["max_body_size"] is not None and (
        module.params["protocol"] in ["udp"] or module.params["type"] == "graphite"
    ):
        module.fail_json(
            msg="The 'max_body_size' parameter is only available for 'influxdb' with http v2 api."
        )

    if (
        module.params["protocol"] != "https"
        and module.params["verify_certificate"] is not None
    ):
        module.fail_json(
            msg="The 'verify_certificate' parameter is only available for 'influxdb' with https."
        )

    server = ProxmoxMetricServer(module)

    changed = False
    error = None
    result = {"id": server.id, "state": server.state, "changed": False}
    if server.state == "absent":
        if server.exists():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = server.remove_server()
    elif server.state == "present":
        if not server.exists():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = server.create_server()
        else:
            (updated_fields, error) = server.modify_server()

            if updated_fields:
                changed = True
                result["updated_fields"] = updated_fields

    # Very gross hack to ignore the error message when Proxmox tries to remove non-existent credentials file
    # See : https://forum.proxmox.com/threads/interface-comes-up-with-all-question-marks.83287/post-382099
    # TODO: Check if the error message is still appearing in version < 7.4-17
    if error is not None and not error.startswith(f"removing {server.type} credentials file"):
        module.fail_json(name=server.id, msg=error)

    result["changed"] = changed
    module.exit_json(**result)


if __name__ == "__main__":
    main()
