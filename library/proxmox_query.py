#!/usr/bin/python

ANSIBLE_METADATA = {
    "metadata_version": "1.0",
    "status": ["stableinterface"],
    "supported_by": "lae",
}

DOCUMENTATION = """
---
module: proxmox_query

short_description: Uses pvesh to query Proxmox API

options:
    query:
        required: true
        aliases: [ "name" ]
        description:
            - Specifies what resource to query
    type:
        required: False
        default: get
        choices: get,set
        description:
            - Specifies type of query
    option:
        required: False
        description:
            - dict of option

author:
    - Musee Ullah (@lae)
"""

EXAMPLES = """
- name: Query cluster status
  proxmox_query:
    query: cluster/status
- name: Apply sdn controller changes && reload
  proxmox_query:
    query: cluster/sdn
    type: set
- name: Collect a list of running LXC containers for some hosts
  proxmox_query:
    query: "nodes/{{ item }}/lxc"
  loop:
    - node01
    - node02
    - node03
"""

RETURN = """
response:
    description: JSON response from pvesh provided by a query
    type: json
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh


def main():
    module = AnsibleModule(
        argument_spec=dict(
            query=dict(type="str", required=True, aliases=["name"]),
            type=dict(
                default="get", required=False, choices=["get", "set"], type="str"
            )
        ),
        supports_check_mode=True,
    )
    result = {}
    changed = False
    if module.params["type"] == "get":
        command = pvesh.get(module.params["query"])
    if module.params["type"] == "set":
        if module.check_mode:
            module.exit_json(changed=True)
        command = pvesh.set(module.params["query"])
        changed = True
    try:
        result["response"] = command
    except ProxmoxShellError as e:
        if e.data:
            result["response"] = e.data

        module.fail_json(msg=e.message, status_code=e.status_code, **result)
    result["changed"] = changed
    module.exit_json(**result)


if __name__ == "__main__":
    main()
