[![Build Status](https://travis-ci.org/lae/ansible-role-proxmox.svg?branch=master)](https://travis-ci.org/lae/ansible-role-proxmox)
[![Galaxy Role](https://img.shields.io/badge/ansible--galaxy-proxmox-blue.svg)](https://galaxy.ansible.com/lae/proxmox/)

lae.proxmox
=========

Installs and configures a Proxmox cluster and restricted SSH configuration.

## Quickstart

The primary goal for this role is to lay out the necessities for configuring a 
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
        - {
            role: lae.proxmox,
            proxmox_group: all,
            proxmox_reboot_on_kernel_update: true
          }

Install this role:

    # Changing ownership of the roles directory may be necessary:
    sudo chown $(whoami): /etc/ansible/roles
    ansible-galaxy install lae.proxmox

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

## Example Playbook

This will configure hosts in the group `pve01` as one cluster, as well as 
reboot the machines should the kernel have been updated. (Only recommended to 
set this flag during installation - reboots during operation should occur 
serially during a maintenance period.)

    - hosts: pve01
      become: True
      roles:
        - {
            role: lae.proxmox,
            proxmox_group: pve01,
            proxmox_reboot_on_kernel_update: true
          }

Role Variables
--------------

```
[variable]: [default] #[description/purpose]
proxmox_group: proxmox # host group that contains the Proxmox hosts to be clustered together
proxmox_fetch_directory: fetch/ # local directory used to download root public keys from each host to
proxmox_repository_line: "deb http://download.proxmox.com/debian jessie pve-no-subscription" # apt-repository configuration - change to enterprise if needed (although TODO further configuration may be needed)
proxmox_check_for_kernel_update: true # Runs a script on the host to check kernel versions
proxmox_reboot_on_kernel_update: false # If set to true, will automatically reboot the machine on kernel updates
proxmox_remove_old_kernels: true # Currently removes kernel from main Debian repository
# proxmox_ldap_bind_user: # Setting this and the next variable will configure the LDAP authentication method to use this account for searching for a user
# proxmox_ldap_bind_password:
```

Dependencies
------------

This role does not install NTP, so you should configure NTP yourself, with the `geerlingguy.ntp` role for example.


License
-------

MIT

Author Information
------------------

Musee Ullah <musee.ullah@fireeye.com>

[pve-cluster]: https://pve.proxmox.com/wiki/Proxmox_VE_4.x_Cluster
[install-ansible]: http://docs.ansible.com/ansible/intro_installation.html
