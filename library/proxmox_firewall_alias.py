#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'trickert76'
}

DOCUMENTATION = '''
---
module: proxmox_firewall_alias

short_description: Manages firewall aliases in Proxmox

options:
    name:
        required: true
        description:
            - Name of the alias.
    cidr:
        required: true
        description:
            - CIDR of the alias.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the alias should exist or not.
    comment:
        required: false
        description:
            - Optionally sets the alias's comment in PVE.

author:
    - Thoralf Rickert-Wendt (@trickert76)
'''

EXAMPLES = '''
- name: Create alias for a host
  proxmox_firewall_alias:
    name: myhost
    cidr: 127.0.0.1
- name: Create special host
  proxmox_firewall_alias:
    name: gateway
    cidr: fd80::1
    comment: Our gateway.
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxFirewallAlias(object):
    def __init__(self, module, result):
        self.module = module
        self.result = result
        self.name = module.params['name']
        self.cidr = module.params['cidr']
        self.state = module.params['state']
        self.comment = module.params['comment']

    def lookup(self):
        try:
            return pvesh.get("cluster/firewall/aliases/{}".format(self.name))
        except ProxmoxShellError as e:
            if e.status_code == 400:
                return None
            self.module.fail_json(msg=e.message, status_code=e.status_code, **self.result)

    def remove_alias(self):
        try:
            pvesh.delete("cluster/firewall/aliases/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_alias(self):
        new_alias = {}
        new_alias['name'] = self.name
        new_alias['cidr'] = self.cidr
        if self.comment is not None:
            new_alias['comment'] = self.comment

        try:
            pvesh.create("cluster/firewall/aliases", **new_alias)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_alias(self):
        existing_alias = self.lookup()
        modified_alias = {}
        modified_alias['cidr'] = self.cidr
        if self.comment is not None:
            modified_alias['comment'] = self.comment

        updated_fields = []
        error = None

        for key in modified_alias:
            staged_value = modified_alias.get(key)
            if key not in existing_alias or staged_value != existing_alias.get(key):
                updated_fields.append(key)
                
        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set("cluster/firewall/aliases/{}".format(self.name), **modified_alias)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True),
            cidr=dict(type='str', required=True),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            comment=dict(default=None, type='str'),
        ),
        supports_check_mode=True
    )

    result = {}
    pve = ProxmoxFirewallAlias(module, result)

    before_alias = pve.lookup()

    changed = False
    error = None
    result['name'] = pve.name
    result['state'] = pve.state

    if pve.state == 'absent':
        if before_alias is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.remove_alias()

            if error is not None:
                module.fail_json(name=pve.name, msg=error)
    elif pve.state == 'present':
        if not before_alias:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.create_alias()
        else:
            # modify alias (note: this function is check mode aware)
            (updated_fields, error) = pve.modify_alias()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=pve.name, msg=error)

    result['changed'] = changed

    after_alias = pve.lookup()
    if after_alias is not None:
        result['alias'] = after_alias

    if module._diff:
        if before_alias is None:
            before_alias = ''
        if after_alias is None:
            after_alias = ''
        result['diff'] = dict(before=before_alias, after=after_alias)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
