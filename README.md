[![Galaxy Role](https://img.shields.io/badge/ansible--galaxy-proxmox-blue.svg)](https://galaxy.ansible.com/lae/proxmox/)

lae.proxmox
===========

Installs and configures Proxmox Virtual Environment 6.x/7.x on Debian servers.

This role allows you to deploy and manage single-node PVE installations and PVE
clusters (3+ nodes) on Debian Buster (10) and Bullseye (11). You are able to
configure the following with the assistance of this role:

  - PVE RBAC definitions (roles, groups, users, and access control lists)
  - PVE Storage definitions
  - [`datacenter.cfg`][datacenter-cfg]
  - HTTPS certificates for the Proxmox Web GUI (BYO)
  - PVE repository selection (e.g. `pve-no-subscription` or `pve-enterprise`)
  - Watchdog modules (IPMI and NMI) with applicable pve-ha-manager config
  - ZFS module setup and ZED notification email

With clustering enabled, this role does (or allows you to do) the following:

  - Ensure all hosts can connect to one another as root over SSH
  - Initialize a new PVE cluster (or possibly adopt an existing one)
  - Create or add new nodes to a PVE cluster
  - Setup Ceph on a PVE cluster
  - Create and manage high availability groups

## Support/Contributing

For support or if you'd like to contribute to this role but want guidance, feel
free to join this Discord server: https://discord.gg/cjqr6Fg. Please note, this
is an temporary invite, so you'll need to wait for @lae to assign you a role,
otherwise Discord will remove you from the server when you logout.

## Quickstart

The primary goal for this role is to configure and manage a
[Proxmox VE cluster][pve-cluster] (see example playbook), however this role can
be used to quickly install single node Proxmox servers.

I'm assuming you already have [Ansible installed][install-ansible]. You will
need to use an external machine to the one you're installing Proxmox on
(primarily because of the reboot in the middle of the installation, though I
may handle this somewhat differently for this use case later).

Copy the following playbook to a file like `install_proxmox.yml`:

    - hosts: all
      become: True
      roles:
        - role: geerlingguy.ntp
            ntp_manage_config: true
            ntp_servers:
              - clock.sjc.he.net,
              - clock.fmt.he.net,
              - clock.nyc.he.net
        - role: lae.proxmox
            - pve_group: all
            - pve_reboot_on_kernel_update: true

Install this role and a role for configuring NTP:

    ansible-galaxy install lae.proxmox geerlingguy.ntp

Now you can perform the installation:

    ansible-playbook install_proxmox.yml -i $SSH_HOST_FQDN, -u $SSH_USER

If your `SSH_USER` has a sudo password, pass the `-K` flag to the above command.
If you also authenticate to the host via password instead of pubkey auth, pass
the `-k` flag (make sure you have `sshpass` installed as well). You can set
those variables prior to running the command or just replace them. Do note the
comma is important, as a list is expected (otherwise it'll attempt to look up a
file containing a list of hosts).

Once complete, you should be able to access your Proxmox VE instance at
`https://$SSH_HOST_FQDN:8006`.

## Deploying a fully-featured PVE 7.x cluster

Create a new playbook directory. We call ours `lab-cluster`. Our playbook will
eventually look like this, but yours does not have to follow all of the steps:

```
lab-cluster/
├── files
│   └── pve01
│       ├── lab-node01.local.key
│       ├── lab-node01.local.pem
│       ├── lab-node02.local.key
│       ├── lab-node02.local.pem
│       ├── lab-node03.local.key
│       └── lab-node03.local.pem
├── group_vars
│   ├── all
│   └── pve01
├── inventory
├── roles
│   └── requirements.yml
├── site.yml
└── templates
    └── interfaces-pve01.j2

6 directories, 12 files
```

First thing you may note is that we have a bunch of `.key` and `.pem` files.
These are private keys and SSL certificates that this role will use to configure
the web interface for Proxmox across all the nodes. These aren't necessary,
however, if you want to keep using the signed certificates by the CA that
Proxmox sets up internally. You may typically use Ansible Vault to encrypt the
private keys, e.g.:

    ansible-vault encrypt files/pve01/*.key

This would then require you to pass the Vault password when running the playbook.

Let's first specify our cluster hosts. Our `inventory` file may look like this:

```
[pve01]
lab-node01.local
lab-node02.local
lab-node03.local
```

You could have multiple clusters, so it's a good idea to have one group for each
cluster. Now, let's specify our role requirements in `roles/requirements.yml`:

```
---
- src: geerlingguy.ntp
- src: lae.proxmox
```

We need an NTP role to configure NTP, so we're using Jeff Geerling's role to do
so. You wouldn't need it if you already have NTP configured or have a different
method for configuring NTP.

Now, let's specify some group variables. First off, let's create `group_vars/all`
for setting NTP-related variables:

```
---
ntp_manage_config: true
ntp_servers:
  - lab-ntp01.local iburst
  - lab-ntp02.local iburst
```

Of course, replace those NTP servers with ones you prefer.

Now for the flesh of your playbook, `pve01`'s group variables. Create a file
`group_vars/pve01`, add the following, and modify accordingly for your environment.

```
---
pve_group: pve01
pve_watchdog: ipmi
pve_ssl_private_key: "{{ lookup('file', pve_group + '/' + inventory_hostname + '.key') }}"
pve_ssl_certificate: "{{ lookup('file', pve_group + '/' + inventory_hostname + '.pem') }}"
pve_cluster_enabled: yes
pve_groups:
  - name: ops
    comment: Operations Team
pve_users:
  - name: admin1@pam
    email: admin1@lab.local
    firstname: Admin
    lastname: User 1
    groups: [ "ops" ]
  - name: admin2@pam
    email: admin2@lab.local
    firstname: Admin
    lastname: User 2
    groups: [ "ops" ]
pve_acls:
  - path: /
    roles: [ "Administrator" ]
    groups: [ "ops" ]
pve_storages:
  - name: localdir
    type: dir
    content: [ "images", "iso", "backup" ]
    path: /plop
    maxfiles: 4
pve_ssh_port: 22

interfaces_template: "interfaces-{{ pve_group }}.j2"
```

`pve_group` is set to the group name of our cluster, `pve01` - it will be used
for the purposes of ensuring all hosts within that group can connect to each
other and are clustered together. Note that the PVE cluster name will be set to
this group name as well, unless otherwise specified by `pve_cluster_clustername`.
Leaving this undefined will default to `proxmox`.

`pve_watchdog` here enables IPMI watchdog support and configures PVE's HA
manager to use it. Leave this undefined if you don't want to configure it.

`pve_ssl_private_key` and `pve_ssl_certificate` point to the SSL certificates for
pvecluster. Here, a file lookup is used to read the contents of a file in the
playbook, e.g. `files/pve01/lab-node01.key`. You could possibly just use host
variables instead of files, if you prefer.

`pve_cluster_enabled` enables the role to perform all cluster management tasks.
This includes creating a cluster if it doesn't exist, or adding nodes to the
existing cluster. There are checks to make sure you're not mixing nodes that
are already in existing clusters with different names.

`pve_groups`, `pve_users`, and `pve_acls` authorizes some local UNIX users (they
must already exist) to access PVE and gives them the Administrator role as part
of the `ops` group. Read the **User and ACL Management** section for more info.

`pve_storages` allows to create different types of storage and configure them.
The backend needs to be supported by [Proxmox][pvesm]. Read the **Storage
Management** section for more info.

`pve_ssh_port` allows you to change the SSH port. If your SSH is listening on
a port other than the default 22, please set this variable. If a new node is
joining the cluster, the PVE cluster needs to communicate once via SSH.

`pve_manage_ssh` (default true) allows you to disable any changes this module
would make to your SSH server config. This is useful if you use another role
to manage your SSH server. Note that setting this to false is not officially
supported, you're on your own to replicate the changes normally made in
`ssh_cluster_config.yml` and `pve_add_node.yml`.

`interfaces_template` is set to the path of a template we'll use for configuring
the network on these Debian machines. This is only necessary if you want to
manage networking from Ansible rather than manually or via each host in PVE.
You should probably be familiar with Ansible prior to doing this, as your method
may involve setting host variables for the IP addresses for each host, etc.

Let's get that interface template out of the way. Feel free to skip this file
(and leave it undefined in `group_vars/pve01`) otherwise. Here's one that I use:

```
# {{ ansible_managed }}
auto lo
iface lo inet loopback

allow-hotplug enp2s0f0
iface enp2s0f0 inet manual

auto vmbr0
iface vmbr0 inet static
    address {{ lookup('dig', ansible_fqdn) }}
    gateway 10.4.0.1
    netmask 255.255.255.0
    bridge_ports enp2s0f0
    bridge_stp off
    bridge_fd 0

allow-hotplug enp2s0f1
auto enp2s0f1
iface enp2s0f1 inet static
    address {{ lookup('dig', ansible_hostname + "-clusternet.local") }}
    netmask 255.255.255.0
```

You might not be familiar with the `dig` lookup, but basically here we're doing
an A record lookup for each machine (e.g. lab-node01.local) for the first
interface (and configuring it as a bridge we'll use for VM interfaces), and then
another slightly modified lookup for the "clustering" network we might use for
Ceph ("lab-node01-clusternet.local"). Of course, yours may look completely
different, especially if you're using bonding, three different networks for
management/corosync, storage and VM traffic, etc.

Finally, let's write our playbook. `site.yml` will look something like this:

```
---
- hosts: all
  become: True
  roles:
    - geerlingguy.ntp

# Leave this out if you're not modifying networking through Ansible
- hosts: pve01
  become: True
  serial: 1
  tasks:
    - name: Install bridge-utils
      apt:
        name: bridge-utils

    - name: Configure /etc/network/interfaces
      template:
        src: "{{ interfaces_template }}"
        dest: /etc/network/interfaces
      register: _configure_interfaces

    - block:
      - name: Reboot for networking changes
        shell: "sleep 5 && shutdown -r now 'Networking changes found, rebooting'"
        async: 1
        poll: 0

      - name: Wait for server to come back online
        wait_for_connection:
          delay: 15
      when: _configure_interfaces is changed

- hosts: pve01
  become: True
  roles:
    - lae.proxmox
```

Basically, we run the NTP role across all hosts (you might want to add some
non-Proxmox machines), configure networking on `pve01` with our separate cluster
network and bridge layout, reboot to make those changes take effect, and then
run this Proxmox role against the hosts to setup a cluster.

At this point, our playbook is ready and we can run the playbook.

Ensure that roles and dependencies are installed:

    ansible-galaxy install -r roles/requirements.yml --force
    pip install jmespath dnspython

`jmespath` is required for some of the tasks involving clustering. `dnspython`
is only required if you're using a `dig` lookup, which you probably won't be if
you skipped configuring networking. We pass `--force` to `ansible-galaxy` here
so that roles are updated to their latest versions if already installed.

Now run the playbook:

    ansible-playbook -i inventory site.yml -e '{"pve_reboot_on_kernel_update": true}'

The `-e '{"pve_reboot_on_kernel_update": true}'` should mainly be run the first
time you do the Proxmox cluster setup, as it'll reboot the server to boot into
a PVE kernel. Subsequent runs should leave this out, as you want to sequentially
reboot servers after the cluster is running.

To specify a particular user, use `-u root` (replacing `root`), and if you need
to provide passwords, use `-k` for SSH password and/or `-K` for sudo password.
For example:

    ansible-playbook -i inventory site.yml -K -u admin1

This will ask for a sudo password, then login to the `admin1` user (using public
key auth - add `-k` for pw) and run the playbook.

That's it! You should now have a fully deployed Proxmox cluster. You may want
to create Ceph storage on it afterwards (see Ceph for more info) and other
tasks possibly, but the hard part is mostly complete.


## Example Playbook

This will configure hosts in the group `pve01` as one cluster, as well as
reboot the machines should the kernel have been updated. (Only recommended to
set this flag during installation - reboots during operation should occur
serially during a maintenance period.) It will also enable the IPMI watchdog.

    - hosts: pve01
      become: True
      roles:
        - role: geerlingguy.ntp
            ntp_manage_config: true
            ntp_servers:
              - clock.sjc.he.net,
              - clock.fmt.he.net,
              - clock.nyc.he.net
        - role: lae.proxmox
            pve_group: pve01
            pve_cluster_enabled: yes
            pve_reboot_on_kernel_update: true
            pve_watchdog: ipmi

## Role Variables

```
[variable]: [default] #[description/purpose]
pve_group: proxmox # host group that contains the Proxmox hosts to be clustered together
pve_repository_line: "deb http://download.proxmox.com/debian/pve bullseye pve-no-subscription" # apt-repository configuration - change to enterprise if needed (although TODO further configuration may be needed)
pve_remove_subscription_warning: true # patches the subscription warning messages in proxmox if you are using the community edition
pve_extra_packages: [] # Any extra packages you may want to install, e.g. ngrep
pve_run_system_upgrades: false # Let role perform system upgrades
pve_run_proxmox_upgrades: true # Let role perform Proxmox VE upgrades
pve_check_for_kernel_update: true # Runs a script on the host to check kernel versions
pve_reboot_on_kernel_update: false # If set to true, will automatically reboot the machine on kernel updates
pve_reboot_on_kernel_update_delay: 60 # Number of seconds to wait before and after a reboot process to proceed with next task in cluster mode
pve_remove_old_kernels: true # Currently removes kernel from main Debian repository
pve_watchdog: none # Set this to "ipmi" if you want to configure a hardware watchdog. Proxmox uses a software watchdog (nmi_watchdog) by default.
pve_watchdog_ipmi_action: power_cycle # Can be one of "reset", "power_cycle", and "power_off".
pve_watchdog_ipmi_timeout: 10 # Number of seconds the watchdog should wait
pve_zfs_enabled: no # Specifies whether or not to install and configure ZFS packages
# pve_zfs_options: "" # modprobe parameters to pass to zfs module on boot/modprobe
# pve_zfs_zed_email: "" # Should be set to an email to receive ZFS notifications
pve_zfs_create_volumes: [] # List of ZFS Volumes to create (to use as PVE Storages). See section on Storage Management.
pve_ceph_enabled: false # Specifies wheter or not to install and configure Ceph packages. See below for an example configuration.
pve_ceph_repository_line: "deb http://download.proxmox.com/debian/ceph-pacific bullseye main" # apt-repository configuration. Will be automatically set for 6.x and 7.x (Further information: https://pve.proxmox.com/wiki/Package_Repositories)
pve_ceph_network: "{{ (ansible_default_ipv4.network +'/'+ ansible_default_ipv4.netmask) | ipaddr('net') }}" # Ceph public network
# pve_ceph_cluster_network: "" # Optional, if the ceph cluster network is different from the public network (see https://pve.proxmox.com/pve-docs/chapter-pveceph.html#pve_ceph_install_wizard)
pve_ceph_nodes: "{{ pve_group }}" # Host group containing all Ceph nodes
pve_ceph_mon_group: "{{ pve_group }}" # Host group containing all Ceph monitor hosts
pve_ceph_mgr_group: "{{ pve_ceph_mon_group }}" # Host group containing all Ceph manager hosts
pve_ceph_mds_group: "{{ pve_group }}" # Host group containing all Ceph metadata server hosts
pve_ceph_osds: [] # List of OSD disks
pve_ceph_pools: [] # List of pools to create
pve_ceph_fs: [] # List of CephFS filesystems to create
pve_ceph_crush_rules: [] # List of CRUSH rules to create
# pve_ssl_private_key: "" # Should be set to the contents of the private key to use for HTTPS
# pve_ssl_certificate: "" # Should be set to the contents of the certificate to use for HTTPS
pve_roles: [] # Added more roles with specific privileges. See section on User Management.
pve_groups: [] # List of group definitions to manage in PVE. See section on User Management.
pve_users: [] # List of user definitions to manage in PVE. See section on User Management.
pve_storages: [] # List of storages to manage in PVE. See section on Storage Management.
pve_datacenter_cfg: {} # Dictionary to configure the PVE datacenter.cfg config file.
```

To enable clustering with this role, configure the following variables appropriately:

```
pve_cluster_enabled: no # Set this to yes to configure hosts to be clustered together
pve_cluster_clustername: "{{ pve_group }}" # Should be set to the name of the PVE cluster
pve_manage_hosts_enabled : yes # Set this to no to NOT configure hosts file (case of using vpn and hosts file is already configured)
```

The following variables are used to provide networking information to corosync.
These are known as ring0_addr/ring1_addr or link0_addr/link1_addr, depending on
PVE version. They should be IPv4 or IPv6 addresses. For more information, refer
to the [Cluster Manager][pvecm-network] chapter in the PVE Documentation.

```
# pve_cluster_addr0: "{{ defaults to the default interface ipv4 or ipv6 if detected }}"
# pve_cluster_addr1: "another interface's IP address or hostname"
```

You can set options in the datacenter.cfg configuration file:

```
pve_datacenter_cfg:
  keyboard: en-us
```

You can also configure [HA manager groups][ha-group]:
```
pve_cluster_ha_groups: [] # List of HA groups to create in PVE.
```

This example creates a group "lab_node01" for resources assigned to the
lab-node01 host:
```
pve_cluster_ha_groups:
  - name: lab_node01
    comment: "My HA group"
    nodes: "lab-node01"
    nofailback: 0
    restricted: 0
```

All configuration options supported in the datacenter.cfg file are documented
in the [Proxmox manual datacenter.cfg section][datacenter-cfg].

In order for live reloading of network interfaces to work via the PVE web UI,
you need to install the `ifupdown2` package. Note that this will remove
`ifupdown`. You can specify this using the `pve_extra_packages` role variable.

## Dependencies

This role does not install NTP, so you should configure NTP yourself, e.g. with
the `geerlingguy.ntp` role as shown in the example playbook.

When clustering is enabled, this role makes use of the `json_query` filter,
which requires that the `jmespath` library be installed on your control host.
You can either `pip install jmespath` or install it via your distribution's
package manager, e.g. `apt-get install python-jmespath`.

## User and ACL Management

You can use this role to manage users and groups within Proxmox VE (both in
single server deployments and cluster deployments). Here are some examples.

```
pve_groups:
  - name: Admins
    comment: Administrators of this PVE cluster
  - name: api_users
  - name: test_users
pve_users:
  - name: root@pam
    email: postmaster@pve.example
  - name: lae@pam
    email: lae@pve.example
    firstname: Musee
    lastname: Ullah
    groups: [ "Admins" ]
  - name: pveapi@pve
    password: "Proxmox789"
    groups:
      - api_users
  - name: testapi@pve
    password: "Test456"
    enable: no
    groups:
      - api_users
      - test_users
  - name: tempuser@pam
    expire: 1514793600
    groups: [ "test_users" ]
    comment: "Temporary user set to expire on 2018年  1月  1日 月曜日 00:00:00 PST"
    email: tempuser@pve.example
    firstname: Test
    lastname: User
```

Refer to `library/proxmox_user.py` [link][user-module] and
`library/proxmox_group.py` [link][group-module] for module documentation.

For managing roles and ACLs, a similar module is employed, but the main
difference is that most of the parameters only accept lists (subject to
change):

```
pve_roles:
  - name: Monitoring
    privileges:
      - "Sys.Modify"
      - "Sys.Audit"
      - "Datastore.Audit"
      - "VM.Monitor"
      - "VM.Audit"
pve_acls:
  - path: /
    roles: [ "Administrator" ]
    groups: [ "Admins" ]
  - path: /pools/testpool
    roles: [ "PVEAdmin" ]
    users:
      - pveapi@pve
    groups:
      - test_users
```

Refer to `library/proxmox_role.py` [link][user-module] and
`library/proxmox_acl.py` [link][acl-module] for module documentation.

## Storage Management

You can use this role to manage storage within Proxmox VE (both in
single server deployments and cluster deployments). For now, the only supported
types are `dir`, `rbd`, `nfs`, `cephfs`, `lvm`,`lvmthin`, and `zfspool`.
Here are some examples.

```
pve_storages:
  - name: dir1
    type: dir
    content: [ "images", "iso", "backup" ]
    path: /ploup
    disable: no
    maxfiles: 4
  - name: ceph1
    type: rbd
    content: [ "images", "rootdir" ]
    nodes: [ "lab-node01.local", "lab-node02.local" ]
    username: admin
    pool: rbd
    krbd: yes
    monhost:
      - 10.0.0.1
      - 10.0.0.2
      - 10.0.0.3
  - name: nfs1
    type: nfs
    content: [ "images", "iso" ]
    server: 192.168.122.2
    export: /data
  - name: lvm1
    type: lvm
    content: [ "images", "rootdir" ]
    vgname: vg1
  - name: lvmthin1
    type: lvmthin
    content: [ "images", "rootdir" ]
    vgname: vg2
    thinpool: data
  - name: cephfs1
    type: cephfs
    content: [ "snippets", "vztmpl", "iso" ]
    nodes: [ "lab-node01.local", "lab-node02.local" ]
    monhost:
      - 10.0.0.1
      - 10.0.0.2
      - 10.0.0.3
  - name: zfs1
    type: zfspool
    content: [ "images", "rootdir" ]
    pool: rpool/data
    sparse: true
```

Currently the `zfspool` type can be used only for `images` and `rootdir` contents.
If you want to store the other content types on a ZFS volume, you need to specify
them with type `dir`, path `/<POOL>/<VOLUME>` and add an entry in
`pve_zfs_create_volumes`. This example adds a `iso` storage on a ZFS pool:

```
pve_zfs_create_volumes:
  - rpool/iso
pve_storages:
  - name: iso
    type: dir
    path: /rpool/iso
    content: [ "iso" ]
```

Refer to `library/proxmox_storage.py` [link][storage-module] for module
documentation.

## Ceph configuration

*This section could use a little more love. If you are actively using this role
to manage your PVE Ceph cluster, please feel free to flesh this section more
thoroughly and open a pull request! See issue #68.*

**PVE Ceph management with this role is experimental.** While users have
successfully used this role to deploy PVE Ceph, it is not fully tested in CI
(due to a lack of usable block devices to use as OSDs in Travis CI). Please
deploy a test environment with your configuration first prior to prod, and
report any issues if you run into any.

This role can configure the Ceph storage system on your Proxmox hosts. The
following definitions show some of the configurations that are possible.

```
pve_ceph_enabled: true
pve_ceph_network: '172.10.0.0/24'
pve_ceph_cluster_network: '172.10.1.0/24'
pve_ceph_nodes: "ceph_nodes"
pve_ceph_osds:
  # OSD with everything on the same device
  - device: /dev/sdc
  # OSD with block.db/WAL on another device
  - device: /dev/sdd
    block.db: /dev/sdb1
  # encrypted OSD with everything on the same device
  - device: /dev/sdc
    encrypted: true
  # encrypted OSD with block.db/WAL on another device
  - device: /dev/sdd
    block.db: /dev/sdb1
    encrypted: true
# Crush rules for different storage classes
# By default 'type' is set to host, you can find valid types at
# (https://docs.ceph.com/en/latest/rados/operations/crush-map/)
# listed under 'TYPES AND BUCKETS'
pve_ceph_crush_rules:
  - name: replicated_rule
    type: osd # This is an example of how you can override a pre-existing rule
  - name: ssd
    class: ssd
    type: osd
    min-size: 2
    max-size: 8
  - name: hdd
    class: hdd
    type: host
# 2 Ceph pools for VM disks which will also be defined as Proxmox storages
# Using different CRUSH rules
pve_ceph_pools:
  - name: ssd
    pgs: 128
    rule: ssd
    application: rbd
    storage: true
# This Ceph pool uses custom size/replication values
  - name: hdd
    pgs: 32
    rule: hdd
    application: rbd
    storage: true
    size: 2
    min-size: 1
# This Ceph pool uses custom autoscale mode : "off" | "on" | "warn"> (default = "warn")
  - name: vm-storage
    pgs: 128
    rule: replicated_rule
    application: rbd
    autoscale_mode: "on"
    storage: true
pve_ceph_fs:
# A CephFS filesystem not defined as a Proxmox storage
  - name: backup
    pgs: 64
    rule: hdd
    storage: false
    mountpoint: /srv/proxmox/backup
```

`pve_ceph_network` by default uses the `ipaddr` filter, which requires the
`netaddr` library to be installed and usable by your Ansible controller.

`pve_ceph_nodes` by default uses `pve_group`, this parameter allows to specify
on which nodes install Ceph (e.g. if you don't want to install Ceph on all your
nodes).

`pve_ceph_osds` by default creates unencrypted ceph volumes. To use encrypted
volumes the parameter `encrypted` has to be set per drive to `true`.

## Developer Notes

When developing new features or fixing something in this role, you can test out
your changes by using Vagrant (only libvirt is supported currently). The
playbook can be found in `tests/vagrant` (so be sure to modify group variables
as needed). Be sure to test any changes on both Debian 10 and 11 (update the
Vagrantfile locally to use `debian/buster64`) before submitting a PR.

You can also specify an apt caching proxy (e.g. `apt-cacher-ng`, and it must
run on port 3142) with the `APT_CACHE_HOST` environment variable to speed up
package downloads if you have one running locally in your environment. The
vagrant playbook will detect whether or not the caching proxy is available and
only use it if it is accessible from your network, so you could just
permanently set this variable in your development environment if you prefer.

For example, you could run the following to show verbose/easier to read output,
use a caching proxy, and keep the VMs running if you run into an error (so that
you can troubleshoot it and/or run `vagrant provision` after fixing):

    APT_CACHE_HOST=10.71.71.10 ANSIBLE_STDOUT_CALLBACK=debug vagrant up --no-destroy-on-error

## Contributors

Musee Ullah ([@lae](https://github.com/lae), <lae@lae.is>) - Main developer  
Fabien Brachere ([@Fbrachere](https://github.com/Fbrachere)) - Storage config support  
Gaudenz Steinlin ([@gaundez](https://github.com/gaudenz)) - Ceph support, etc  
Richard Scott ([@zenntrix](https://github.com/zenntrix)) - Ceph support, PVE 7.x support, etc  
Thoralf Rickert-Wendt ([@trickert76](https://github.com/trickert76)) - PVE 6.x support, etc  
Engin Dumlu ([@roadrunner](https://github.com/roadrunner))  
Jonas Meurer ([@mejo-](https://github.com/mejo-))  
Ondrej Flidr ([@SniperCZE](https://github.com/SniperCZE))  
niko2 ([@niko2](https://github.com/niko2))  
Christian Aublet ([@caublet](https://github.com/caublet))  
Michael Holasek ([@mholasek](https://github.com/mholasek))  

[pve-cluster]: https://pve.proxmox.com/wiki/Cluster_Manager
[install-ansible]: http://docs.ansible.com/ansible/intro_installation.html
[pvecm-network]: https://pve.proxmox.com/pve-docs/chapter-pvecm.html#_separate_cluster_network
[pvesm]: https://pve.proxmox.com/pve-docs/chapter-pvesm.html
[user-module]: https://github.com/lae/ansible-role-proxmox/blob/master/library/proxmox_user.py
[group-module]: https://github.com/lae/ansible-role-proxmox/blob/master/library/proxmox_group.py
[acl-module]: https://github.com/lae/ansible-role-proxmox/blob/master/library/proxmox_group.py
[storage-module]: https://github.com/lae/ansible-role-proxmox/blob/master/library/proxmox_storage.py
[datacenter-cfg]: https://pve.proxmox.com/wiki/Manual:_datacenter.cfg
[ceph_volume]: https://github.com/ceph/ceph-ansible/blob/master/library/ceph_volume.py
[ha-group]: https://pve.proxmox.com/wiki/High_Availability#ha_manager_groups
