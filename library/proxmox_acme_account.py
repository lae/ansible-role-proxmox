#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_acme_account
short_description: Manages ACME configs/account registrations in Proxmox
options:
    name:
        default: "default"
        description:
            - Name of the ACME config to manage.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the ACME account config should exist or not.
    directory:
        required: false
        default: https://acme-v02.api.letsencrypt.org/directory
        description:
            - Specifies which ACME directory to register against.
    contact:
        required: true
        description:
            - Sets the contact email for the ACME account.
author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Create default ACME configuration
  proxmox_acme_account:
    contact: hello@example.com
- name: Create secondary ACME configuration on staging
  proxmox_acme_account:
    name: secondary
    directory: https://acme-staging-v02.api.letsencrypt.org/directory
    contact: test@example.com
'''

RETURN = '''
updated_fields:
    description: Fields that were modified for an existing account config
    type: list
account:
    description: Information about the account fetched from PVE after this task completed. (output for this is currently disabled since it contains a private key)
    type: json
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxACMEAccount(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.directory = module.params['directory']
        self.contact = module.params['contact']

    def lookup(self):
        try:
            return pvesh.get("cluster/acme/account/{}".format(self.name))
        except ProxmoxShellError as e:
            if e.status_code == 400:
                return None
            self.module.fail_json(msg=e.message, status_code=e.status_code)

    def identify_tos(self):
        try:
            return pvesh.get("cluster/acme/tos")
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

    def remove_account(self):
        try:
            pvesh.delete("cluster/acme/account/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_account(self):
        new_account = {
            'name': self.name,
            'directory': self.directory,
            'contact': self.contact,
            'tos_url': self.identify_tos()
        }

        try:
            pvesh.create("cluster/acme/account/", **new_account)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_account(self):
        lookup = self.lookup()

        updated_fields = []
        recreate_account = False
        error = None

        if lookup['account']['contact'][0].split(':')[1] != self.contact:
            updated_fields.append('contact')

        if lookup['directory'] != self.directory:
            updated_fields.append('directory')
            recreate_account = True

        if lookup['tos'] != self.identify_tos():
            updated_fields.append('tos')
            recreate_account = True

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields, would_recreate=recreate_account)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, recreate_account, error)

        try:
            if recreate_account:
                self.remove_account()
                self.create_account()
            else:
                pvesh.set("cluster/acme/account/{}".format(self.name), contact=self.contact)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, recreate_account, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(default='default', type='str'),
            state=dict(choices=['present', 'absent'], default='present', type='str'),
            directory=dict(default='https://acme-v02.api.letsencrypt.org/directory', type='str'),
            contact=dict(default=None, required=True, type='str'),
        ),
        supports_check_mode=True
    )

    account = ProxmoxACMEAccount(module)

    changed = False
    error = None
    result = {}
    result['name'] = account.name
    result['state'] = account.state

    if account.state == 'absent':
        if account.lookup() is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = account.remove_account()

            if error is not None:
                module.fail_json(name=account.name, msg=error)
    elif account.state == 'present':
        if not account.lookup():
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = account.create_account()
        else:
            # modify account (note: this function is check mode aware)
            (updated_fields, recreate_account, error) = account.modify_account()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields
                result['account_recreated'] = recreate_account

        if error is not None:
            module.fail_json(name=account.name, msg=error)

    """
    # The following contains sensitive data, so for now don't include it in the
    # module output. I think there's a flag to check for that lets you decide
    # how to handle outputting of sensitive output that we should use here.
    lookup = account.lookup()
    if lookup is not None:
        result['account'] = lookup
    """

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()