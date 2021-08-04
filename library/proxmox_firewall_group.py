#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['stableinterface'],
    'supported_by': 'trickert76'
}

DOCUMENTATION = '''
---
module: proxmox_firewall_group

short_description: Manages firewall group of rules in Proxmox

options:
    name:
        required: true
        description:
            - Name of the group.
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
    rules:
        required: true
        description:
            - a list of rules that should be applied. Every item is a dict of a rule.

author:
    - Thoralf Rickert-Wendt (@trickert76)
'''

EXAMPLES = '''
- name: Create group of rules for a host
  proxmox_firewall_group:
    name: proxmox
    comment: rules for all proxmox hosts
    rules:
      - action: ACCEPT
        type: in
        pos: 0
        enable: true
        source: +proxmox
        dest: +proxmox
        proto: tcp
        dport: 22
        comment: 'ipset proxmox can talk to ipset proxmox'
        log: nolog
      - action: ACCEPT
        type: in
        pos: 1
        enable: true
        source: +network
        dest: +proxmox
        macro: DNS
        comment: 'ipset network can talk to ipset proxmox'
        log: nolog
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxFirewallGroup(object):
    def __init__(self, module, result):
        self.module = module
        self.result = result
        self.name = module.params['name']
        self.state = module.params['state']
        self.comment = module.params['comment']
        self.rules = module.params['rules']
        
        for pos, rule in enumerate(self.rules, start=0):
            rule['pos'] = pos
    
    def create_rule(self, rule):
        new_rule = {}
        new_rule['pos'] = rule['pos']

        if 'action' in rule:
            new_rule['action'] = rule['action']
        else:
            new_rule['action'] = 'ACCEPT'
        if 'type' in rule:
            new_rule['type'] = rule['type']
        else:
            new_rule['type'] = 'in'
        if 'enable' in rule and not bool(rule['enable']):
            new_rule['enable'] = 0
        else:
            new_rule['enable'] = 1
        if 'source' in rule:
            new_rule['source'] = rule['source']
        if 'dest' in rule:
            new_rule['dest'] = rule['dest']
        if 'macro' in rule:
            new_rule['macro'] = rule['macro']
        if 'proto' in rule:
            new_rule['proto'] = rule['proto']
        if 'dport' in rule:
            new_rule['dport'] = rule['dport']
        if 'sport' in rule:
            new_rule['sport'] = rule['sport']
        if 'comment' in rule:
            new_rule['comment'] = rule['comment']
        if 'log' in rule:
            new_rule['log'] = rule['log']
        else:
            new_rule['log'] = 'nolog'
        return new_rule

    def get_existing_rule(self, ruleset, pos):
        for rule in ruleset:
            if str(rule['pos']) == str(pos):
                return rule
        return None

    def lookup(self):
        try:
            groups = pvesh.get("cluster/firewall/groups")
            for group in groups:
              if group['group'] == self.name:
                group['rules'] = []
                positions = pvesh.get("cluster/firewall/groups/{}".format(self.name))
                for position in positions:
                  rule = pvesh.get("cluster/firewall/groups/{}/{}".format(self.name,position['pos']))
                  if 'digest' in rule:
                    del rule['digest']
                  group['rules'].append(rule)
                return group
            return None
            return pvesh.get("cluster/firewall/groups/{}".format(self.name))
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code, **self.result)

    def remove_group(self):
        try:
            pvesh.delete("cluster/firewall/groups/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def create_group(self):
        new_group = {}
        new_group['group'] = self.name
        if self.comment is not None:
            new_group['comment'] = self.comment

        try:
            pvesh.create("cluster/firewall/groups", **new_group)
            if self.rules is not None:
                for rule in list(reversed(self.rules)):
                  new_rule = self.create_rule(rule)
                  pvesh.create("cluster/firewall/groups/{}/".format(self.name), **new_rule)
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

    def modify_group(self):
        existing_group = self.lookup()
        modified_group = {}
        if self.comment is not None:
            modified_group['comment'] = self.comment

        updated_fields = []
        error = None

        for key in modified_group:
            staged_value = modified_group.get(key)
            if key not in existing_group or staged_value != existing_group.get(key):
                updated_fields.append(key)
        
        if self.rules is not None and 'rules' in existing_group:
            for rule in self.rules:
                new_rule = self.create_rule(rule)
                existing_rule = self.get_existing_rule(existing_group['rules'],new_rule['pos'])
                
                if existing_rule is None:
                    updated_fields.append('rules')
                    break
                if new_rule != existing_rule:
                    updated_fields.append('rules')
                    break
                
        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            # no set handler defined
            # pvesh.set("cluster/firewall/groups/{}".format(self.name), **modified_group)
            
            if self.rules is not None and 'rules' in existing_group:
                for rule in self.rules:
                    new_rule = self.create_rule(rule)
                    existing_rule = self.get_existing_rule(existing_group['rules'], new_rule['pos'])
                    
                    if existing_rule is None:
                        pvesh.create("cluster/firewall/groups/{}/".format(self.name), **new_rule)
                    #else:
                        #pvesh.set("cluster/firewall/groups/{}/{}".format(self.name,new_rule['pos']))

                for rule in existing_group['rules']:
                    new_rule = self.get_existing_rule(self.rules, rule['pos'])
                    
                    #if new_rule is None:
                        #pvesh.delete("cluster/firewall/groups/{}/{}".format(self.name,rule['pos']))
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
            rules=dict(type='list', required=True),
            assign_cluster=dict(type='bool', default=False),
            assign_hosts=dict(type='list', required=False),
            assign_vms=dict(type='list', required=False),
        ),
        supports_check_mode=True
    )

    result = {}
    pve = ProxmoxFirewallGroup(module, result)

    before_group = pve.lookup()

    changed = False
    error = None
    result['name'] = pve.name
    result['state'] = pve.state

    if pve.state == 'absent':
        if before_group is not None:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.remove_group()

            if error is not None:
                module.fail_json(name=pve.name, msg=error)
    elif pve.state == 'present':
        if not before_group:
            if module.check_mode:
                module.exit_json(changed=True)

            (changed, error) = pve.create_group()
        else:
            # modify group (note: this function is check mode aware)
            (updated_fields, error) = pve.modify_group()

            if updated_fields:
                changed = True
                result['updated_fields'] = updated_fields

        if error is not None:
            module.fail_json(name=pve.name, msg=error)

    result['changed'] = changed

    after_group = pve.lookup()
    if after_group is not None:
        result['group'] = after_group

    if module._diff:
        if before_group is None:
            before_group = ''
        if after_group is None:
            after_group = ''
        result['diff'] = dict(before=before_group, after=after_group)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
