#!/usr/bin/python

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'lae'
}

DOCUMENTATION = '''
---
module: proxmox_query

short_description: Uses pvesh to query Proxmox API

options:
    query:
        required: true
        aliases: [ "name" ]
        description:
            - Specifies what resource to query

author:
    - Musee Ullah (@lae)
'''

EXAMPLES = '''
- name: Query cluster status
  proxmox_query:
    query: cluster/status
- name: Collect a list of running LXC containers for some hosts
  proxmox_query:
    query: "nodes/{{ item }}/lxc"
  with_items:
    - node01
    - node02
    - node03
'''

RETURN = '''
response:
    description: JSON response from pvesh provided by a query
    type: json
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

def main():
    module = AnsibleModule(
        argument_spec = dict(
            query=dict(type='str', required=True, aliases=['name']),
        ),
        supports_check_mode=True
    )

    result = {"changed": False}

    try:
        result['response'] = pvesh.get(module.params['query'])
    except ProxmoxShellError as e:
        if e.data:
            result["response"] = e.data

        module.fail_json(msg=e.message, status_code=e.status_code, **result)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
