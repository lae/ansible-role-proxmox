#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_group

short_description: Manages groups in Proxmox

options:
    name:
        required: true
        aliases: [ "group", "groupid" ]
        description:
            - Name of the PVE group to manage.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the group should exist or not.
    comment:
        required: false
        description:
            - Optionally sets the group's comment in PVE.

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Create Administrators group
  proxmox_group:
    name: Administrators
- name: Create API Users group
  proxmox_group:
    name: api_users
    comment: Users allowed to access the API.
'''

RETURN = '''
updated_fields:
    description: Fields that were modified for an existing group
    type: list
group:
    description: Information about the group fetched from PVE after this task completed.
    type: json
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxGroup(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.comment = module.params['comment']

    def lookup(self):
        try:
            return pvesh.get("access/groups/{}".format(self.name))
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code, **result)

    def remove_group(self):
        try:
            pvesh.delete("access/groups/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_group(self):
        new_group = {}
        if self.comment is not None:
            new_group['comment'] = self.comment

        try:
            pvesh.create("access/groups", groupid=self.name, **new_group)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_group(self):
        lookup = self.lookup()
        staged_group = {}

        if self.comment is not None:
            staged_group['comment'] = self.comment

        updated_fields = []
        error = None

        for key in staged_group:
            staged_value = to_text(staged_group[key]) if isinstance(staged_group[key], str) else staged_group[key]
            if key not in lookup or staged_value != lookup[key]:
                updated_fields.append(key)

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set("access/groups/{}".format(self.name), **staged_group)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True, aliases=['group', 'groupid']),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            comment=dict(default=None, type='str'),
        ),
        supports_check_mode=True
    )

    group = ProxmoxGroup(module)

    changed = False
    error = None
    result = {}
    result['name'] = group.name
    result['state'] = group.state

    if group.state == 'absent':
        if group.lookup() is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = group.remove_group()

            if error is not None:
                module.fail_json(name=group.name, msg=error)
    elif group.state == 'present':
        if not group.lookup():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = group.create_group()
        else:
            # modify group (note: this function is check mode aware)
            (updated_fields, error) = group.modify_group()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=group.name, msg=error)

    lookup = group.lookup()
    if lookup is not None:
        result['group'] = lookup

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()
