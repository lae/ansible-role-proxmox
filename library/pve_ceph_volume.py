#!/usr/bin/python

from ansible.module_utils.basic import AnsibleModule
import datetime

ANSIBLE_METADATA = {
    'metadata_version': '1.0',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ceph_volume

short_description: Query ceph OSDs with ceph-volume

description:
    - Using the ceph-volume utility available in Ceph this module
      can be used to query ceph OSDs that are backed by logical volumes.
    - Only available in ceph versions luminous or greater.

options:
    cluster:
        description:
            - The ceph cluster name.
        required: false
        default: ceph
    data:
        description:
            - The logical volume name or device to use for the OSD data.
        required: true
    data_vg:
        description:
            - If data is a lv, this must be the name of the volume group it belongs to.
        required: false

author:
    - Andrew Schoen (@andrewschoen)
    - Sebastien Han <seb@redhat.com>
'''

EXAMPLES = '''
- name: query all osds
  ceph_volume:

- name: query single osd on test cluster
  ceph_volume:
    cluster: test
    data: /dev/sdc
'''

def exec_command(module, cmd, stdin=None):
    '''
    Execute command(s)
    '''
    binary_data = False
    if stdin:
        binary_data = True
    rc, out, err = module.run_command(cmd, data=stdin, binary_data=binary_data)
    return rc, cmd, out, err

def get_data(data, data_vg):
    if data_vg:
        data = '{0}/{1}'.format(data_vg, data)
    return data


def list_osd(module):
    '''
    List will detect whether or not a device has Ceph LVM Metadata
    '''

    # get module variables
    cluster = module.params['cluster']
    data = module.params.get('data', None)
    data_vg = module.params.get('data_vg', None)
    data = get_data(data, data_vg)

    # Build the CLI
    action = ['lvm', 'list']
    cmd = ['ceph-volume', '--cluster', cluster]
    cmd.extend(action)
    if data:
        cmd.append(data)
    cmd.append('--format=json')

    return cmd


def run_module():
    module_args = dict(
        cluster=dict(type='str', required=False, default='ceph'),
        data=dict(type='str', required=False),
        data_vg=dict(type='str', required=False),
    )

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = dict(
        changed=False,
        stdout='',
        stderr='',
        rc=0,
        start='',
        end='',
        delta='',
    )

    if module.check_mode:
        module.exit_json(**result)

    # start execution
    startd = datetime.datetime.now()

    # List Ceph LVM Metadata on a device
    rc, cmd, out, err = exec_command(module, list_osd(module))

    endd = datetime.datetime.now()
    delta = endd - startd

    result = dict(
        cmd=cmd,
        start=str(startd),
        end=str(endd),
        delta=str(delta),
        rc=rc,
        stdout=out.rstrip('\r\n'),
        stderr=err.rstrip('\r\n'),
        changed=False,
    )

    if rc != 0:
        module.fail_json(msg='non-zero return code', **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
