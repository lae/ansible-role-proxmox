#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'trickert76'
}

DOCUMENTATION = '''
---
module: proxmox_firewall_rule

short_description: Manages firewall assignments of rule of rules to hosts and vms in Proxmox

options:
    name:
        required: true
        description:
            - Name of the group.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the group should exist or not.
    qemu:
        required: false
        description:
            - a vm id where this group of rules should be applied, needs node too
    node:
        required: false
        description:
            - a node name where this group of rules should be applied
    cluster:
        required: false
        description:
            - true, if this group should be applied to the cluster

author:
    - Thoralf Rickert-Wendt (@trickert76)
'''

EXAMPLES = '''
- name: Assign group of rules for a cluster
  proxmox_firewall_rule:
    name: proxmox
    cluster: true
- name: Assign group of rules for a host
  proxmox_firewall_rule:
    name: proxmox
    node: node1
- name: Assign group of rules for a host
  proxmox_firewall_rule:
    name: vm
    node: node1
    qemu: 100
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxFirewallRule(object):
    def __init__(self, module, result):
        self.module = module
        self.result = result
        self.name = module.params['name']
        self.state = module.params['state']
        self.cluster = module.params['cluster']
        self.node = module.params['node']
        self.qemu = module.params['qemu']
        
        if bool(self.cluster):
          self.type = 'cluster'
        elif self.qemu is not None:
          self.type = 'qemu'
        elif self.node is not None:
          self.type = 'node'
        else:
          self.module.fail_json(msg='unknown type, neither cluster nore node or qemu is defined', **self.result)
    
    def define_base_url(self):
        if self.type == 'cluster':
            url = "cluster/firewall/rules"
        elif self.type == 'node':
            url = "nodes/{}/firewall/rules".format(self.node)
        elif self.type == "qemu":
            url = "nodes/{}/qemu/{}/firewall/rules".format(self.node,self.qemu)
        
        return url
    
    def lookup(self):
        try:
            url = self.define_base_url()
            
            positions = pvesh.get(url)
            for position in positions:
                rule = pvesh.get("{}/{}".format(url,position['pos']))
                if rule['type'] == 'group' and rule['action'] == self.name:
                    return rule
            return None
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code, **self.result)

    def remove_rule(self, before_role):
        try:
            url = self.define_base_url()
            pvesh.delete("{}/{}".format(url,before_role['pos']))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_rule(self):
        new_rule = {}
        new_rule['enable'] = 1
        new_rule['type'] = 'group'
        new_rule['action'] = self.name

        try:
            url = self.define_base_url()
            pvesh.create(url, **new_rule)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_rule(self, existing_rule):
        existing_rule = self.lookup()
        modified_rule = {}
        modified_rule['enable'] = 1
        modified_rule['type'] = 'group'
        modified_rule['action'] = self.name

        updated_fields = []
        error = None

        for key in modified_rule:
            staged_value = modified_rule.get(key)
            if key not in existing_rule or staged_value != existing_rule.get(key):
                updated_fields.append(key)
        
        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set(url.format(existing_rule['pos']), **modified_rule)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            cluster=dict(type='bool', default=False),
            node=dict(type='str', required=False),
            qemu=dict(type='str', required=False),
        ),
        supports_check_mode=True
    )

    result = {}
    pve = ProxmoxFirewallRule(module, result)

    before_role = pve.lookup()

    changed = False
    error = None
    result['name'] = pve.name
    result['state'] = pve.state
    result['type'] = pve.type

    if pve.state == 'absent':
        if before_role is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.remove_rule(before_role)

            if error is not None:
                module.fail_json(name=pve.name, msg=error)
    elif pve.state == 'present':
        if not before_role:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.create_rule()
        else:
            # modify rule (note: this function is check mode aware)
            (updated_fields, error) = pve.modify_rule(before_role)

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=pve.name, msg=error)

    result['changed'] = changed

    after_rule = pve.lookup()
    if after_rule is not None:
        result['rule'] = after_rule

    if module._diff:
        if before_role is None:
            before_role = ''
        if after_rule is None:
            after_rule = ''
        result['diff'] = dict(before=before_role, after=after_rule)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
