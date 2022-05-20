#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'futuriste'
}

DOCUMENTATION = '''
---
module: proxmox_pool

short_description: Manages pools in Proxmox

options:
    name:
        required: true
        aliases: [ "pool", "poolid" ]
        description:
            - Name of the PVE pool to manage.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the pool should exist or not.
    comment:
        required: false
        description:
            - Optionally sets the pool's comment in PVE.

author:
    - Guiffo Joel (@futuriste)
'''

EXAMPLES = '''
- name: Create Administrators pool
  proxmox_pool:
    name: Administrators
- name: Create Dev Users pool's
  proxmox_pool:
    name: pool_dev
    comment: Dev Users allowed to access on this pool.
'''

RETURN = '''
updated_fields:
    description: Fields that were modified for an existing pool
    type: list
pool:
    description: Information about the pool fetched from PVE after this task completed.
    type: json
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxPool(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.comment = module.params['comment']

    def lookup(self):
        try:
            return pvesh.get("pools/{}".format(self.name))
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code, **result)

    def remove_pool(self):
        try:
            pvesh.delete("pools/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_pool(self):
        new_pool = {}
        if self.comment is not None:
            new_pool['comment'] = self.comment

        try:
            pvesh.create("pools", poolid=self.name, **new_pool)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_pool(self):
        lookup = self.lookup()
        staged_pool = {}

        if self.comment is not None:
            staged_pool['comment'] = self.comment

        updated_fields = []
        error = None

        for key in staged_pool:
            staged_value = to_text(staged_pool[key]) if isinstance(staged_pool[key], str) else staged_pool[key]
            if key not in lookup or staged_value != lookup[key]:
                updated_fields.append(key)

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set("pools/{}".format(self.name), **staged_pool)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True, aliases=['pool', 'poolid']),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            comment=dict(default=None, type='str'),
        ),
        supports_check_mode=True
    )

    pool = ProxmoxPool(module)

    changed = False
    error = None
    result = {}
    result['name'] = pool.name
    result['state'] = pool.state

    if pool.state == 'absent':
        if pool.lookup() is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pool.remove_pool()

            if error is not None:
                module.fail_json(name=pool.name, msg=error)
    elif pool.state == 'present':
        if not pool.lookup():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pool.create_pool()
        else:
            # modify pool (note: this function is check mode aware)
            (updated_fields, error) = pool.modify_pool()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=pool.name, msg=error)

    lookup = pool.lookup()
    if lookup is not None:
        result['pool'] = lookup

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()