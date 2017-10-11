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
            - API endpoint to query
        required: true

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Query cluster status
  proxmox_query:
    name: cluster.status
'''

RETURN = '''
response:
    description: Response JSON from pvesh query
    type: json
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
        self.password = module.params['password']A

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
            password=dict(default=None, type='str')
        ),
        supports_check_mode=True
    )


    if module.check_mode:
        return result

    pve = ProxmoxAPI(backend='local')

    try:
        # maybe sanitize this later
        result['response'] = eval("pve.{}".format(module.params['name'])).get()
    except proxmoxer.core.ResourceException:
        module.fail_json(msg='Failed to execute get query with pvesh.', **result)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
