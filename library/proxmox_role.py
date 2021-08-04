#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_role
short_description: Manages the Access Control List in Proxmox
options:
    name:
        required: true
        description:
            - name of the role.
    privileges:
        required: true
        type: list
        description:
            - Specifies a list of PVE privileges for the given role.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether this role should exist or not.
author:
    - Thoralf Rickert-Wendt (@trickert76)
'''

EXAMPLES = '''
- name: Create a role for monitoring with given privileges
  proxmox_role:
    name: "monitoring"
    privileges: [ "Sys.Modify", "Sys.Audit", "Datastore.Audit", "VM.Monitor", "VM.Audit" ]
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxRole(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.privileges = module.params['privileges']
        self.state = module.params['state']

        try:
            self.existing_roles = pvesh.get("access/roles")
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

        self.parse_roles()

    def parse_roles(self):
        self.roles = []
        for existing_role in self.existing_roles:
          self.roles.append(existing_role.get('roleid'))

    def lookup(self):
        self.roles = []
        for existing_role in self.existing_roles:
          if existing_role.get('roleid') == self.name:
            args = {}
            args['roleid'] = existing_role.get('roleid')
            args['privs'] = ','.join(sorted(existing_role.get('privs').split(',')))
            return args

        return None

    def exists(self):
        if self.name not in self.roles:
          return False

        return True

    def prepare_role_args(self, appendKey=True):
        args = {}
        if appendKey:
          args['roleid'] = self.name
        args['privs'] = ','.join(sorted(self.privileges))

        return args

    def remove_role(self):
        try:
            pvesh.delete("access/roles/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_role(self):
        new_role = self.prepare_role_args()

        try:
            pvesh.create("access/roles", **new_role)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_role(self):
        existing_role = self.lookup()
        modified_role = self.prepare_role_args(appendKey=False)
        updated_fields = []
        error = None

        for key in modified_role:
            if key not in existing_role:
                updated_fields.append(key)
            else:
                new_value = modified_role.get(key)
                old_value = existing_role.get(key)
                if isinstance(old_value, list):
                    old_value = ','.join(sorted(old_value))
                if isinstance(new_value, list):
                    new_value = ','.join(sorted(new_value))

                if new_value != old_value:
                    updated_fields.append(key)

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set("access/roles/{}".format(self.name), **modified_role)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True),
            privileges=dict(type='list', required=True),
            state=dict(default='present', choices=['present', 'absent'], type='str')
        ),
        supports_check_mode=True
    )

    role = ProxmoxRole(module)

    changed = False
    error = None
    result = {}
    result['name'] = role.name
    result['state'] = role.state
    result['changed'] = False

    if role.state == 'absent':
        if role.exists():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = role.remove_role()
    elif role.state == 'present':
        if not role.exists():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = role.create_role()
        else:
            (updated_fields, error) = role.modify_role()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

    if error is not None:
        module.fail_json(name=role.name, msg=error)

    result['changed'] = changed
    module.exit_json(**result)

if __name__ == '__main__':
    main()