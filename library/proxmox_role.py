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
- name: Allow Admins group Administrator access to /
  proxmox_role:
    name: "monitoring"
    privileges: [ "Sys.Modify", "Sys.Audit", "Datastore.Audit", "VM.Monitor", "VM.Audit" ]
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
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
        constituents = []

        self.roles = []
        for role in self.existing_roles:
          self.roles.append(role.roleid)
          

    def exists(self):
        if self.name not in self.roles:
          return False

        return True

    def prepare_role_args(self):
        args = {}
        args['roleid'] = self.name
        args['privs'] = ','.join(self.privileges)

        return args

    def set_role(self, delete=0):
        args = self.prepare_acl_args()

        try:
            pvesh.set("access/roles", delete=delete, **args)
            return None
        except ProxmoxShellError as e:
            return e.message

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

    error = None
    result = {}
    result['state'] = role.state
    result['changed'] = False

    if role.state == 'absent':
        if role.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)

            error = role.set_role(delete=1)
    elif acl.state == 'present':
        if not role.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)

            error = role.set_role()

    if error is not None:
        module.fail_json(path=acl.path, msg=error)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
