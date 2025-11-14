#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    "metadata_version": "0.1",
    "status": ["preview"],
    "supported_by": "spieICS",
}

DOCUMENTATION = """
---
module: proxmox_sdn

short_description: Manages sdn in Proxmox

options:
    type:
        required: true
        choices: ["qinq", "simple", "vlan", "vxlan"]
        type: str
        description:
            - The SDN Zone type
    name:
        required: true
        type: str
        description:
            - The SDN zone object identifier
    mtu:
        required: false
        type: integer
        description:
            - MTU for zones
    ipam:
        required: false
        type: str
        description:
            - Use specific ipam
    peers:
        required: true
        use: vxlan
        type: list
        description:
            - peers adress list
    tag:
        required: true
        use: vlan
        type: str
        description:
            - Service-VLAN Tag
    bridge:
        required: true
        use: vlan,qinq
        type: str
        description:
            - Vlan: The local bridge or OVS switch
            - qinq: A local, VLAN-aware bridge
    nodes:
        required: false
        use: simple,vlan,qinq,vxlan
        type: str
        description:
            - List of cluster node names
    state:
        required: false
        default: "present"
        use: all
        choices: [ "present", "absent" ]
        description:
            - Specifies whether this sdn object should exist or not.
    vlan_protocol:
        required: true
        default: None
        use: qinq
        type: str
        choices: [ "802.1q", "802.ad" ]
        description:
            - vlan-protocol
author:
    - SpieICS - automation team
"""
EXAMPLES = """
- name: Provide vxlan
  proxmox_sdn:
    type: vxlan
    name: vxlan1
    peers:
      - ip1
      - ip2
      ...
    mtu: 1450
    ipam: pve
    nodes: ""
    state: present

- name: Provide simple
  proxmox_sdn:
    type: simple
    name: simple1
    nodes:
        - node1
        - node2
        - node3
      ...
    state: present
- name: Provide Vlan
  proxmox_sdn:
    type: vlan
    name: vlan1
    nodes:
        - node1
        - node2
        - node3
      ...
    mtu: 1450
    bridge: vmbr0
    state: present
- name: Provide qinq
  proxmox_sdn:
    type: qinq
    name: qinq1
    tag: 10
    nodes:
        - node1
        - node2
        - node3
      ...
    mtu: 1450
    bridge: vmbr0
    state: present
- name: Provide vnet
  proxmox_sdn:
    type: vnets
    name: vnet1
    zone: vxlan1
    tag: 10 # The unique VLAN or VXLAN ID
    vlanaware: false
    alias: str with regex (?^i:[\(\)-_.\w\d\s]{0,256})
    state: present
"""

RETURN = """
"""

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh
import sys


class ProxmoxSDN(object):
    def __init__(self, module):
        self.module = module
        self.type = module.params["type"]
        self.name = module.params["name"]
        self.mtu = module.params["mtu"]
        self.ipam = module.params["ipam"]
        self.peers = module.params["peers"]
        self.state = module.params["state"]
        self.tag = module.params["tag"]
        self.bridge = module.params["bridge"]
        self.nodes = module.params["nodes"]
        self.vlan_protocol = module.params["vlan_protocol"]
        self.alias = module.params["alias"]
        self.zone = module.params["zone"]
        self.vlanaware = module.params["vlanaware"]
        if module.params["type"] == "vnets":
            self.api_path = "vnets"
        else:
            self.api_path = "zones"

    def lookup(self):
        try:
            sdn_object_list = pvesh.get("cluster/sdn/{}".format(self.api_path))
            for item in sdn_object_list:
                if self.api_path == "vnets":
                    if item["vnet"] == self.name:
                        return item
                else:
                    if item["zone"] == self.name:
                        return item
            return False
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

    def prepare_sdn_args(self):
        """Prepare arguments for creating or modifying an SDN object"""
        args = {}
        if self.peers is not None:
            args["peers"] = ",".join(self.peers)
        if self.mtu is not None:
            args["mtu"] = self.mtu
        if self.ipam is not None:
            args["ipam"] = self.ipam
        if self.tag is not None:
            args["tag"] = self.tag
        if self.bridge is not None:
            args["bridge"] = self.bridge
        if self.nodes is not None:
            args["nodes"] = ",".join(self.nodes)
        if self.vlan_protocol is not None:
            args["vlan-protocol"] = self.vlan_protocol
        if self.alias is not None:
            args["alias"] = self.alias
        if self.zone is not None:
            args["zone"] = self.zone
        if self.vlanaware is not None:
            args["vlanaware"] = 1 if self.zone else 0
        return args

    def remove_sdn(self):
        try:
            pvesh.delete("cluster/sdn/{}/{}".format(self.api_path, self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_sdn(self):
        """Create a new SDN object"""
        new_object = self.prepare_sdn_args()
        try:
            if self.type == "vnets":
                pvesh.create(
                    "cluster/sdn/{}".format(self.api_path),
                    vnet=self.name,
                    **new_object
                )
            else:
                pvesh.create(
                    "cluster/sdn/{}".format(self.api_path),
                    type=self.type,
                    zone=self.name,
                    **new_object
                )
            return (True, None)
        except ProxmoxShellError as e:
            return (True, e.message)

    def modify_sdn(self, module):
        """Modify an existing SDN object"""

        updated_fields = []
        staged_sdn = {}
        new_object = self.prepare_sdn_args()
        lookup = self.lookup()
        error = None

        for key in new_object:
            if key == "peers":
                if set(self.peers) != set(lookup.get("peers", "").split(",")):
                    updated_fields.append(key)
                    staged_sdn[key] = new_object[key]
            elif key == "nodes":
                if set(self.nodes) != set(lookup.get("nodes", "").split(",")):
                    updated_fields.append(key)
                    staged_sdn[key] = new_object[key]
            else:
                new_value = (
                    to_text(new_object[key])
                    if isinstance(new_object[key], str)
                    else new_object[key]
                )
                if key not in lookup or new_value != lookup[key]:
                    updated_fields.append(key)
                    staged_sdn[key] = new_object[key]
        if not updated_fields:
            return (updated_fields, None)
        try:
            pvesh.set(
                "cluster/sdn/{}/{}".format(self.api_path, self.name), **staged_sdn
            )
        except ProxmoxShellError as e:
            return (None, e.message)
        return (updated_fields, error)


def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module_args = dict(
        type=dict(
            default=None,
            type="str",
            choices=["qinq", "simple", "vlan", "vxlan", "vnets"],
        ),
        name=dict(type="str"),
        mtu=dict(default=None, type="int"),
        ipam=dict(default=None, type="str"),
        state=dict(default="present", choices=["present", "absent"], type="str"),
        peers=dict(default=None, type="list"),
        bridge=dict(default=None, type="str"),
        tag=dict(default=None, type="int"),
        nodes=dict(default=None, type="list"),
        vlan_protocol=dict(default=None, choices=["802.1q", "802.ad"], type="str"),
        alias=dict(default=None, type="str"),
        zone=dict(default=None, type="str"),
        vlanaware=dict(default=None, type="bool"),
    )
    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ["type", "qinq", ["type", "name", "state", "bridge", "tag"]],
            ["type", "simple", ["type", "name", "state"]],
            ["type", "vlan", ["type", "name", "state", "bridge"]],
            ["type", "vxlan", ["type", "name", "state", "peers"]],
            ["type", "vnets", ["type", "name", "state", "zone"]],
        ],
    )
    sdn = ProxmoxSDN(module)
    changed = False
    error = None
    result = {}
    result["type"] = sdn.type
    result["state"] = sdn.state

    if sdn.state == "absent":
        if sdn.lookup() is not None:
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = sdn.remove_sdn()

    elif sdn.state == "present":
        if not sdn.lookup():
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = sdn.create_sdn()
        else:
            (updated_fields, error) = sdn.modify_sdn(module)

            if updated_fields:
                changed = True
                result["updated_fields"] = updated_fields

        if error is not None:
            module.fail_json(name=sdn.name, msg=error)

    lookup = sdn.lookup()

    if lookup:
        result["name"] = lookup

    result["changed"] = changed

    module.exit_json(**result)


if __name__ == "__main__":
    main()
