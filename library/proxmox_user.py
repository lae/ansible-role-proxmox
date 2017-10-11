#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_user

short_description: Manages user accounts in Proxmox

options:
    name:
        description:
            - User ID
        required: true

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from proxmoxer import ProxmoxAPI

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

        self.cluster = ProxmoxAPI(backend='local')

    def user_exists(self):
        try:
            if self.cluster.access.users.get(self.name):
                return True
        except:
            return False

    def user_info(self):
        if not self.user_exists():
            return False
        return self.cluster.access.users.get(self.name)

    def check_groups_exist(self):
        # Checks to see if groups specified already exist or not
        if self.groups is not None:
            groups = [group['groupid'] for group in self.cluster.access.groups.get()]
            return set(self.groups).issubset(set(groups))
        else:
            return True

    def prepare_user_args(self):
        args = {}

        args['enable'] = 1 if self.enable else 0
        args['expire'] = self.expire

        if self.comment is not None:
            args['comment'] = self.comment.replace(' ', '\ ')

        if self.firstname is not None:
            args['firstname'] = self.firstname.replace(' ', '\ ')

        if self.lastname is not None:
            args['lastname'] = self.lastname.replace(' ', '\ ')

        if self.email is not None:
            args['email'] = self.email

        if self.groups is not None:
            args['groups'] = ','.join(self.groups)

        return args

    def remove_user(self):
        try:
            self.cluster.access.users.delete(self.name)
            return (True, None)
        except:
            return (False, "Failed to run pvesh delete for user.")

    def create_user(self):
        new_user = self.prepare_user_args()

        if self.password is not None:
            new_user['password'] = self.password.replace(' ', '\ ')

        if not self.check_groups_exist():
            return (False, "One or more specified groups do not exist.")

        try:
            self.cluster.access.users.create(userid=self.name, **new_user)
            return (True, None)
        except:
            return (False, "Failed to run pvesh create for this user.")

    def modify_user(self):
        current_user = self.user_info()
        updated_user = self.prepare_user_args()

        changes_needed = False

        for key in updated_user:
            if key == 'groups':
                if self.groups != current_user['groups']:
                    changes_needed = True
            else:
                # honestly get rid of this cruft either by fixing proxmoxer or removing it as a dep/embedding pvesh commands in here directly
                update = updated_user[key].replace('\ ', ' ') if type(updated_user[key]) is str else updated_user[key]
                if update != current_user[key]:
                    changes_needed = True

        if self.module.check_mode and changes_needed:
            self.module.exit_json(changed=True)

        if not changes_needed:
            # No changes necessary
            return (False, None)

        if not self.check_groups_exist():
            return (False, "One or more specified groups do not exist.")

        try:
            self.cluster.access.users(self.name).put(**updated_user)
            return (True, None)
        except:
            return (False, "Failed to run pvesh create for this user.")

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
            expire=dict(default=0, type='int'),
            firstname=dict(default=None, type='str'),
            lastname=dict(default=None, type='str'),
            password=dict(default=None, type='str', no_log=True)
        ),
        supports_check_mode=True
    )

    user = ProxmoxUser(module)

    changed = False
    error = None
    result = {}
    result['name'] = user.name
    result['state'] = user.state

    if user.state == 'absent':
        if user.user_exists():
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = user.remove_user()
            if error is not None:
                module.fail_json(name=user.name, msg=error)
    elif user.state == 'present':
        if not user.user_exists():
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = user.create_user()
        else:
            # modify user (note: this function is check mode aware)
            (changed, err) = user.modify_user()
        if error is not None:
            module.fail_json(name=user.name, msg=error)
        if user.password is not None:
            result['password'] = 'NOT_LOGGING_PASSWORD'

    if user.user_exists():
        result['user'] = user.user_info()

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()
