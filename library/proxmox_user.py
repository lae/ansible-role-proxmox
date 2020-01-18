#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '0.2',
    'status': ['preview'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_user

short_description: Manages user accounts in Proxmox

options:
    name:
        required: true
        aliases: [ "user", "userid" ]
        description:
            - Name and realm of the user to create, e.g. C(operator@pam) and
              C(pveapi@pve).
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the user should exist or not.
    enable:
        required: false
        default: yes
        type: bool
        description:
            - Whether or not the user should be enabled in PVE.
    groups:
        required: false
        type: list
        description:
            - Specifies a list of PVE groups that this user should belong to.
    comment:
        required: false
        description:
            - Optionally sets the user's comment in PVE.
    email:
        required: false
        description:
            - Optionally sets the user's email in PVE.
    firstname:
        required: false
        description:
            - Optionally sets the user's first name in PVE.
    lastname:
        required: false
        description:
            - Optionally sets the user's last name in PVE.
    password:
        required: false
        description:
            - Optionally sets the user's password in PVE. Note that this is only
              used during the creation of a user to specify their initial
              password, thus cannot be used to change a password of a user that
              already exists (due to a limitation of the API, I believe). This
              also only applies to the C(pve) realm as well, probably.
    expire:
        required: false
        default: 0
        type: int
        description:
            - Account expiration date (seconds since epoch). C(0) means no
              expiration date.

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Create PVE user with an initial password that expires at the beginning of 2018
  proxmox_user:
    name: helloworld@pve
    expire: 1514793600
    password: helloworld
    firstname: Hello
    lastname: World
    comment: A hello world user.
    groups:[ "test_users" ]
- name: Another way of defining groups
  proxmox_user:
    name: admin@pve
    password: "{{ vaulted_password }}"
    groups:
      - Administrators
      - APIUsers
- name: Add email for root user
  proxmox_user:
    name: root@pam
    email: root@mail.example
- name: Disable a user
  proxmox_user:
    name: baduser@pam
    enable: no
- name: Ensure a user does not exist
  proxmox_user:
    name: ghost@pve
    state: absent
'''

RETURN = '''
updated_fields:
    description: Fields that were modified for an existing user
    type: list
user:
    description: Information about the user fetched from PVE after this task completed.
    type: json
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxUser(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.enable = module.params['enable']
        self.groups = module.params['groups']
        self.comment = module.params['comment']
        self.email = module.params['email']
        self.expire = module.params['expire']
        self.firstname = module.params['firstname']
        self.lastname = module.params['lastname']
        self.password = module.params['password']

    def lookup(self):
        try:
            return pvesh.get("access/users/{}".format(self.name))
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

    def check_groups_exist(self):
        # Checks to see if groups specified already exist or not
        if self.groups is not None:
            try:
                groups = [group['groupid'] for group in pvesh.get("access/groups")]
                return set(self.groups).issubset(set(groups))
            except ProxmoxShellError as e:
                self.module.fail_json(msg=e.message, status_code=e.status_code)

        return True

    def prepare_user_args(self):
        args = {}

        args['enable'] = 1 if self.enable else 0
        args['expire'] = self.expire

        if self.comment is not None:
            args['comment'] = self.comment

        if self.firstname is not None:
            args['firstname'] = self.firstname

        if self.lastname is not None:
            args['lastname'] = self.lastname

        if self.email is not None:
            args['email'] = self.email

        if self.groups is not None:
            args['groups'] = ','.join(self.groups)

        return args

    def remove_user(self):
        try:
            pvesh.delete("access/users/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_user(self):
        new_user = self.prepare_user_args()

        if self.password is not None:
            new_user['password'] = self.password

        if not self.check_groups_exist():
            return (False, "One or more specified groups do not exist.")

        try:
            pvesh.create("access/users", userid=self.name, **new_user)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_user(self):
        lookup = self.lookup()
        staged_user = self.prepare_user_args()

        updated_fields = []
        error = None

        for key in staged_user:
            if key == 'groups':
                # Since staged_user['groups'] is already converted to a string,
                # we check our object instead
                if set(self.groups) != set(lookup['groups']):
                    updated_fields.append(key)
            else:
                staged_value = to_text(staged_user[key]) if isinstance(staged_user[key], str) else staged_user[key]
                if key not in lookup or staged_value != lookup[key]:
                    updated_fields.append(key)

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        if not self.check_groups_exist():
            error = "One or more specified groups do not exist."
        else:
            try:
                pvesh.set("access/users/{}".format(self.name), **staged_user)
            except ProxmoxShellError as e:
                error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True, aliases=['user', 'userid']),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            enable=dict(default='yes', type='bool'),
            groups=dict(default=None, type='list'),
            comment=dict(default=None, type='str'),
            email=dict(default=None, type='str'),
            firstname=dict(default=None, type='str'),
            lastname=dict(default=None, type='str'),
            password=dict(default=None, type='str', no_log=True),
            expire=dict(default=0, type='int')
        ),
        supports_check_mode=True
    )

    user = ProxmoxUser(module)

    changed = False
    error = None
    result = {}
    result['name'] = user.name
    result['state'] = user.state

    if user.password is not None:
        result['password'] = 'NOT_LOGGING_PASSWORD'

    if user.state == 'absent':
        if user.lookup() is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = user.remove_user()

            if error is not None:
                module.fail_json(name=user.name, msg=error)
    elif user.state == 'present':
        if not user.lookup():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = user.create_user()
        else:
            # modify user (note: this function is check mode aware)
            (updated_fields, error) = user.modify_user()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=user.name, msg=error)

    lookup = user.lookup()
    if lookup:
        result['user'] = lookup

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()
