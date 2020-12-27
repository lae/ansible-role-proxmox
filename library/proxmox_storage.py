#!/usr/bin/python
# -*- coding: utf-8 -*-

ANSIBLE_METADATA = {
    'metadata_version': '0.1',
    'status': ['preview'],
    'supported_by': 'fbrachere'
}

DOCUMENTATION = '''
---
module: proxmox_storage

short_description: Manages the storage in Proxmox

options:
    name:
        required: true
        aliases: [ "storage", "storageid" ]
        description:
            - Name of the storage.
    type:
        required: true
        aliases: [ "storagetype" ]
        choices: [ "dir", "nfs", "rbd", "lvm", "lvmthin", "cephfs", "zfspool" ]
        description:
            - Type of storage, must be supported by Proxmox.
    disable:
        required: false
        description: Disable the storage.
    state:
        required: false
        default: "present"
        choices: [ "present", "absent" ]
        description:
            - Specifies whether this storage should exist or not.
    content:
        required: true
        aliases: [ "storagecontent" ]
        type: list
        choices: [ "images", "rootdir", "vztmpl", "backup", "iso", "snippets" ]
        description:
            - Contents supported by the storage, not all storage
            types support all content types.
    nodes:
        required: false
        type: list
        description:
            - List of cluster node names where this storage is usable.
    path:
        required: false
        description:
            - File system path.
    pool:
        required: false
        description:
            - Ceph/ZFS pool name.
    monhost:
        required: false
        type: list
        description:
            - Monitor addresses of the ceph cluster.
    username:
        required: false
        description:
            - User name (RBD) who access to ceph cluster.
    krbd:
        required: false
        default: 0
        description:
            - Always access rbd through krbd kernel module.
    maxfiles:
        required: false
        default: 0
        description:
            - Maximal number of backup files per VM. 0 for unlimited.
    export:
        required: false
        description:
            - NFS export path
    server:
        required: false
        description:
            - Server IP or DNS name.
    options:
        required: false
        description:
            - NFS mount options.
    vgname:
        required: false
        description:
            - LVM volume group name. This must point to an existing volume group.
    thinpool:
        required: false
        description:
            - The name of the LVM thin pool.
    sparse:
        required: false
        description:
            - Use ZFS thin-provisioning.

author:
    - Fabien Brachere (@fbrachere)
'''

EXAMPLES = '''
- name: Create a directory storage type
  proxmox_storage:
    name: dir1
    type: dir
    path: /mydir
    content: [ "images", "iso", "backup" ]
    maxfiles: 3
- name: Create an RBD storage type
  proxmox_storage:
    name: ceph1
    type: rbd
    content: [ "images", "rootdir" ]
    nodes: [ "proxmox1", "proxmox2" ]
    username: admin
    pool: rbd
    krbd: yes
    monhost:
      - 10.0.0.1
      - 10.0.0.2
      - 10.0.0.3
- name: Create an NFS storage type
  proxmox_storage:
    name: nfs1
    type: nfs
    content: [ "images", "iso" ]
    server: 192.168.122.2
    export: /data
- name: Create an LVM storage type
  proxmox_storage:
    name: lvm1
    type: lvm
    content: [ "images", "rootdir" ]
    vgname: vg1
- name: Create an LVM-thin storage type
  proxmox_storage:
    name: lvmthin1
    type: lvmthin
    content: [ "images", "rootdir" ]
    vgname: vg2
    thinpool: data
- name: Create an CephFS storage type
  proxmox_storage:
    name: cephfs1
    type: cephfs
    content: [ "snippets", "vztmpl", "iso" ]
    nodes: [ "proxmox1", "proxmox2"]
    monhost:
      - 10.0.0.1
      - 10.0.0.2
      - 10.0.0.3
- name: Create a ZFS storage type
  proxmox_storage:
    name: zfs1
    type: zfspool
    content: [ "images", "rootdir" ]
    pool: rpool/data
    sparse: true
'''

RETURN = '''
'''

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text
from ansible.module_utils.pvesh import ProxmoxShellError
import ansible.module_utils.pvesh as pvesh

class ProxmoxStorage(object):
    def __init__(self, module):
        self.module = module
        self.name = module.params['name']
        self.state = module.params['state']
        self.type = module.params['type']
        self.disable = module.params['disable']
        self.content = module.params['content']
        self.nodes = module.params['nodes']
        self.path = module.params['path']
        self.pool = module.params['pool']
        self.monhost = module.params['monhost']
        self.username = module.params['username']
        self.krbd = module.params['krbd']
        self.maxfiles = module.params['maxfiles']
        self.server = module.params['server']
        self.export = module.params['export']
        self.options = module.params['options']
        self.vgname = module.params['vgname']
        self.thinpool = module.params['thinpool']
        self.sparse = module.params['sparse']

        try:
            self.existing_storages = pvesh.get("storage")
        except ProxmoxShellError as e:
            self.module.fail_json(msg=e.message, status_code=e.status_code)

    def lookup(self):
        for item in self.existing_storages:
            if item['storage'] == self.name:
                # pvesh doesn't return the disable param value if it's false,
                # so we set it to False.
                if item.get('disable') is None:
                    item['disable'] = False
                return item
        return None

    def exists(self):
        for item in self.existing_storages:
            if item["storage"] == self.name:
                return True
        return False

    def prepare_storage_args(self):
        args = {}

        args['type'] = self.type
        args['content'] = ','.join(self.content)
        if self.nodes is not None:
            args['nodes'] = ','.join(self.nodes)
        if self.disable is not None:
            args['disable'] = self.disable
        else:
            args['disable'] = False
        if self.path is not None:
            args['path'] = self.path
        if self.pool is not None:
            args['pool'] = self.pool
        if self.monhost is not None:
            args['monhost'] = ','.join(self.monhost)
        if self.username is not None:
            args['username'] = self.username
        if self.krbd is not None:
            args['krbd'] = self.krbd
        if self.maxfiles is not None:
            args['maxfiles'] = self.maxfiles
        if self.server is not None:
            args['server'] = self.server
        if self.export is not None:
            args['export'] = self.export
        if self.options is not None:
            args['options'] = self.options
        if self.vgname is not None:
            args['vgname'] = self.vgname
        if self.thinpool is not None:
            args['thinpool'] = self.thinpool
        if self.sparse is not None:
            args['sparse'] = self.sparse

        if self.maxfiles is not None and 'backup' not in self.content:
            self.module.fail_json(msg="maxfiles is not allowed when there is no 'backup' in content")
        if self.krbd is not None and self.type != 'rbd':
            self.module.fail_json(msg="krbd is only allowed with 'rbd' storage type")

        return args

    def create_storage(self):
        new_storage = self.prepare_storage_args()
        try:
            pvesh.create("storage", storage=self.name, **new_storage)
            return None
        except ProxmoxShellError as e:
            return e.message

    def modify_storage(self):
        lookup = self.lookup()
        new_storage = self.prepare_storage_args()

        staged_storage = {}
        updated_fields = []
        error = None

        for key in new_storage:
            if key == 'content':
                if set(self.content) != set(lookup.get('content', '').split(',')):
                    updated_fields.append(key)
                    staged_storage[key] = new_storage[key]
            elif key == 'monhost':
                if set(self.monhost) != set(lookup.get('monhost', '').split(',')):
                    updated_fields.append(key)
                    staged_storage[key] = new_storage[key]
            elif key == 'nodes':
                if set(self.nodes) != set(lookup.get('nodes', '').split(',')):
                    updated_fields.append(key)
                    staged_storage[key] = new_storage[key]
            else:
                new_value = to_text(new_storage[key]) if isinstance(new_storage[key], str) else new_storage[key]
                if key not in lookup or new_value != lookup[key]:
                    updated_fields.append(key)
                    staged_storage[key] = new_storage[key]

        if self.module.check_mode:
            self.module.exit_json(changed=bool(updated_fields), expected_changes=updated_fields)

        if not updated_fields:
            # No changes necessary
            return (updated_fields, error)

        try:
            pvesh.set("storage/{}".format(self.name), **staged_storage)
        except ProxmoxShellError as e:
            error = e.message

        return (updated_fields, error)


    def remove_storage(self):
        try:
            pvesh.delete("storage/{}".format(self.name))
            return (True, None)
        except ProxmoxShellError as e:
            return (False, e.message)

def main():
    # Refer to https://pve.proxmox.com/pve-docs/api-viewer/index.html
    module_args = dict(
        name=dict(type='str', required=True, aliases=['storage', 'storageid']),
        content=dict(type='list', required=True, aliases=['storagetype']),
        nodes=dict(type='list', required=False, default=None),
        type=dict(default=None, type='str', required=True,
                  choices=["dir", "nfs", "rbd", "lvm", "lvmthin", "cephfs",
                           "zfspool"]),
        disable=dict(required=False, type='bool', default=False),
        state=dict(default='present', choices=['present', 'absent'], type='str'),
        path=dict(default=None, required=False, type='str'),
        pool=dict(default=None, type='str', required=False),
        monhost=dict(default=None, type='list', required=False),
        username=dict(default=None, type='str', required=False),
        krbd=dict(default=None, type='bool', required=False),
        maxfiles=dict(default=None, type='int', required=False),
        export=dict(default=None, type='str', required=False),
        server=dict(default=None, type='str', required=False),
        options=dict(default=None, type='str', required=False),
        vgname=dict(default=None, type='str', required=False),
        thinpool=dict(default=None, type='str', required=False),
        sparse=dict(default=None, type='bool', required=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ["type", "cephfs", ["content"]],
            ["type", "dir", ["path", "content"]],
            ["type", "rbd", ["pool", "content"]],
            ["type", "nfs", ["server", "content", "export"]],
            ["type", "lvm", ["vgname", "content"]],
            ["type", "lvmthin", ["vgname", "thinpool", "content"]],
            ["type", "zfspool", ["pool", "content"]],
        ]
    )
    storage = ProxmoxStorage(module)

    changed = False
    error = None
    result = {}
    result['state'] = storage.state
    result['changed'] = False

    if storage.state == 'absent':
        if storage.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)
            (changed, error) = storage.remove_storage()
    elif storage.state == 'present':
        if not storage.exists():
            result['changed'] = True
            if module.check_mode:
                module.exit_json(**result)

            error = storage.create_storage()
        else:
            # modify storage (check mode is ok)
            (updated_fields,error) = storage.modify_storage()

            if updated_fields:
                result['changed'] = True
                result['updated_fields'] = updated_fields

    if error is not None:
        module.fail_json(name=storage.name, msg=error)

    module.exit_json(**result)

if __name__ == '__main__':
    main()
