lae.proxmox
=========

Installs and configures a Proxmox cluster and restricted SSH configuration.

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

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: pve01
      become: True
      roles:
        - {
            role: lae.proxmox,
            proxmox_group: pve01,
            proxmox_reboot_on_kernel_update: true
          }

License
-------

MIT

Author Information
------------------

Musee Ullah <musee.ullah@fireeye.com>
