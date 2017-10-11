#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
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
            - Name of the PVE group to manager.
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
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from proxmoxer import ProxmoxAPI

class ProxmoxGroup(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.comment = module.params['comment']

        self.cluster = ProxmoxAPI(backend='local')

    def group_exists(self):
        try:
            if self.cluster.access.groups.get(self.name):
                return True
        except:
            return False

    def group_info(self):
        if not self.group_exists():
            return False
        return self.cluster.access.groups.get(self.name)

    def remove_group(self):
        try:
            self.cluster.access.groups.delete(self.name)
            return (True, None)
        except:
            return (False, "Failed to run pvesh delete for group.")

    def create_group(self):
        new_group = {}
        if self.comment is not None:
            new_group['comment'] = self.comment.replace(' ', '\ ')

        try:
            self.cluster.access.groups.create(groupid=self.name, **new_group)
            return (True, None)
        except:
            return (False, "Failed to run pvesh create for this group.")

    def modify_group(self):
        current_group = self.group_info()
        updated_group = {}
        if self.comment is not None:
            updated_group['comment'] = self.comment.replace(' ', '\ ')

        changes_needed = False

        for key in updated_group:
            if key not in current_group or updated_group[key].replace('\ ', ' ') != current_group[key]:
                changes_needed = True

        if self.module.check_mode and changes_needed:
            self.module.exit_json(changed=True)

        if not changes_needed:
            # No changes necessary
            return (False, None)

        try:
            self.cluster.access.groups(self.name).put(**updated_group)
            return (True, None)
        except:
            return (False, "Failed to run pvesh create for this group.")

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
        if group.group_exists():
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = group.remove_group()
            if error is not None:
                module.fail_json(name=group.name, msg=error)
    elif group.state == 'present':
        if not group.group_exists():
            if module.check_mode:
                module.exit_json(changed=True)
            (changed, error) = group.create_group()
        else:
            # modify group (note: this function is check mode aware)
            (changed, err) = group.modify_group()
        if error is not None:
            module.fail_json(name=group.name, msg=error)

    if group.group_exists():
        result['group'] = group.group_info()

    result['changed'] = changed

    module.exit_json(**result)

if __name__ == '__main__':
    main()
