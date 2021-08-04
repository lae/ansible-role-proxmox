#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'trickert76'
}

DOCUMENTATION = '''
---
module: proxmox_firewall_ipset

short_description: Manages firewall ip sets in Proxmox

options:
    name:
        required: true
        description:
            - Name of the ipset.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether the ipset should exist or not.
    entries:
        required: false
        type: list
        description:
            - Specifies a list of aliases or cidr that should be part of the .
    comment:
        required: false
        description:
            - Optionally sets the ipset's comment in PVE.

author:
    - Thoralf Rickert-Wendt (@trickert76)
'''

EXAMPLES = '''
- name: Create ipset for a host
  proxmox_firewall_ipset:
    name: mygroup
    comment: Our hosts.
    entries:
      - 192.168.10.0/24
      - myaliashost
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxFirewallIPSet(object):
    def __init__(self, module, result):
        self.module = module
        self.result = result
        self.name = module.params['name']
        self.state = module.params['state']
        self.comment = module.params['comment']
        self.entries = module.params['entries']

    def lookup(self):
        try:
            ipsets = pvesh.get("cluster/firewall/ipset")
            for ipset in ipsets:
              if ipset.get('name') == self.name:
                ipset['entries'] = pvesh.get("cluster/firewall/ipset/{}".format(self.name))
                return ipset
            return None
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code, **self.result)

    def remove_ipset(self):
        try:
            pvesh.delete("cluster/firewall/ipset/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_ipset(self):
        new_ipset = {}
        new_ipset['name'] = self.name
        if self.comment is not None:
            new_ipset['comment'] = self.comment

        try:
            pvesh.create("cluster/firewall/ipset", **new_ipset)
            if self.entries is not None:
              for entry in self.entries:
                new_entry = {}
                new_entry['cidr'] = entry
                pvesh.create("cluster/firewall/ipset/{}/".format(self.name), **new_entry)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_ipset(self):
        existing_ipset = self.lookup()
        staged_ipset = {}
        if self.comment is not None:
            staged_ipset['comment'] = self.comment

        updated_fields = []
        error = None

        for key in staged_ipset:
            staged_value = to_text(staged_ipset[key]) if isinstance(staged_ipset[key], str) else staged_ipset[key]
            if key not in existing_ipset or staged_value != existing_ipset.get(key):
                updated_fields.append(key)
        
        if existing_ipset.get('entries') is not None:
            existing_entries = existing_ipset.get('entries')
        else:
            existing_entries = []

        if self.entries is not None:
            for entry in self.entries:
                found = False
                for existing_entry in existing_entries:
                    if entry == existing_entry.get('cidr'):
                        found = True
                        break
                if not found:
                    updated_fields.append('entries')
 
        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            # there is no setter
            # pvesh.set("cluster/firewall/ipset/{}".format(self.name), **staged_ipset)
            
            if self.entries is not None:
                for entry in self.entries:
                    found = False
                    for existing_entry in existing_entries:
                        if entry == existing_entry.get('cidr'):
                            found = True
                            break
                    if not found:
                        new_entry = {}
                        new_entry['cidr'] = entry
                        pvesh.create("cluster/firewall/ipset/{}/".format(self.name), **new_entry)

                for existing_entry in existing_entries:
                    if existing_entry.get('cidr') not in self.entries:
                        pvesh.delete("cluster/firewall/ipset/{}/{}".format(self.name, entry))
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module = AnsibleModule(
        argument_spec = dict(
            name=dict(type='str', required=True),
            state=dict(default='present', choices=['present', 'absent'], type='str'),
            comment=dict(default=None, type='str'),
            entries=dict(type='list')
        ),
        supports_check_mode=True
    )

    result = {}
    pve = ProxmoxFirewallIPSet(module, result)
    
    before_ipset = pve.lookup()

    changed = False
    error = None
    result['name'] = pve.name
    result['state'] = pve.state

    if pve.state == 'absent':
        if before_ipset is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = ipset.remove_ipset()

            if error is not None:
                module.fail_json(name=pve.name, msg=error)
    elif pve.state == 'present':
        if not before_ipset:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.create_ipset()
        else:
            # modify ipset (note: this function is check mode aware)
            (updated_fields, error) = pve.modify_ipset()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=pve.name, msg=error)

    result['changed'] = changed

    after_ipset = pve.lookup()
    if after_ipset is not None:
        result['ipset'] = after_ipset

    if module._diff:
        if before_ipset is None:
            before_ipset = ''
        if after_ipset is None:
            after_ipset = ''
        result['diff'] = dict(before=before_ipset, after=after_ipset)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
