#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_acl

short_description: Manages the Access Control List in Proxmox

options:
    path:
        required: true
        aliases: [ "resource" ]
        description:
            - Location of the resource to apply access control to.
    roles:
        required: true
        type: list
        description:
            - Specifies a list of PVE roles, which contains sets of privileges,
              to allow for this access control.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether this access control should exist or not.
    groups:
        required: false
        type: list
        description:
            - Specifies a list of PVE groups to apply this access control for.
    users:
        required: false
        type: list
        description:
            - Specifies a list of PVE users to apply this access control for.

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Allow Admins group Administrator access to /
  proxmox_acl:
    path: /
    roles: [ "Administrator" ]
    groups: [ "Admins" ]
- name: Allow pveapi@pve and test_users group PVEAdmin access to /pools/testpool
  proxmox_acl:
    path: /pools/testpool
    roles: [ "PVEAdmin" ]
    users:
      - pveapi@pve
    groups:
      - test_users
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxACL(object):
    def __init__(self, module):
        self.module = module
        self.path = module.params['path']
        self.state = module.params['state']
        self.roles = module.params['roles']
        self.groups = module.params['groups']
        self.users = module.params['users']

        try:
            self.existing_acl = pvesh.get("access/acl")
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

        # PVE 5.x (unnecessarily) uses a string for this value. This ensures
        # that it's an integer for when we compare values later.
        for acl in self.existing_acl:
            acl['propagate'] = int(acl['propagate'])

        self.parse_acls()

    def parse_acls(self):
        constituents = []

        if self.users is not None:
            [constituents.append(["user", user]) for user in self.users]

        if self.groups is not None:
            [constituents.append(["group", group]) for group in self.groups]

        self.acls = []
        for role in self.roles:
            for constituent in constituents:
                self.acls.append({
                    "path": self.path,
                    "propagate": 1, # possibly make this configurable in the module later
                    "roleid": role,
                    "type": constituent[0],
                    "ugid": constituent[1]
                })

    def exists(self):
        for acl in self.acls:
            if acl not in self.existing_acl:
                return False

        return True

    def prepare_acl_args(self):
        args = {}
        args['path'] = self.path
        args['roles'] = ','.join(self.roles)

        if self.groups is not None:
            args['groups'] = ','.join(self.groups)

        if self.users is not None:
            args['users'] = ','.join(self.users)

        return args

    def set_acl(self, delete=0):
        acls = self.prepare_acl_args()

        try:
            pvesh.set("access/acl", delete=delete, **acls)
            return None
        except ProxmoxShellError as e:
            return e.message

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            path=dict(type='str', required=True, aliases=['resource']),
            roles=dict(type='list', required=True),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            groups=dict(default=None, type='list'),
            users=dict(default=None, type='list'),
        ),
        required_one_of=[["groups", "users"]],
        supports_check_mode=True
    )

    acl = ProxmoxACL(module)

    error = None
    result = {}
    result['state'] = acl.state
    result['changed'] = False

    if acl.state == 'absent':
        if acl.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)

            error = acl.set_acl(delete=1)
    elif acl.state == 'present':
        if not acl.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)

            error = acl.set_acl()

    if error is not None:
        module.fail_json(path=acl.path, msg=error)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
