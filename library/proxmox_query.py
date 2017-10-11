#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_query

short_description: Queries Proxmox API

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

def run_module():
    module_args = dict(
        name=dict(type='str', required=True),
    )

    result = dict(
        changed=False,
        response=[]
    )

    module = AnsibleModule(
        argument_spec=module_args,
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

def main():
    run_module()

if __name__ == '__main__':
    main()
