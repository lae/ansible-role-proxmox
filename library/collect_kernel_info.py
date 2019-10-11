#!/usr/bin/python
import glob
import re
import subprocess

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils._text import to_text

def main():
    module = AnsibleModule(
        argument_spec = dict(
            lookup_packages = dict(required=False, default=True, type='bool')
        ),
        supports_check_mode=True
    )

    # This module only performs diagnostics, so it doesn't actually change anything
    # During actual usage we return "changed" depending on booted kernel status
    if module.check_mode:
        module.exit_json(changed=False)

    params = module.params

    # Much of the following is reimplemented from /usr/share/grub/grub-mkconfig_lib
    kernels = []
    # Collect a list of possible installed kernels
    for filename in glob.glob("/boot/vmlinuz-*") + glob.glob("/vmlinuz-*") + \
                    glob.glob("/boot/kernel-*"):
        if ".dpkg-" in filename:
            continue
        if filename.endswith(".rpmsave") or filename.endswith(".rpmnew"):
            continue
        kernels.append(filename)

    latest_kernel = ""
    re_prefix = re.compile("[^-]*-")
    re_attributes = re.compile("[._-](pre|rc|test|git|old|trunk)")
    for kernel in kernels:
        right = re.sub(re_attributes, "~\1", re.sub(re_prefix, '', latest_kernel, count=1))
        if not right:
            latest_kernel = kernel
            continue
        left = re.sub(re_attributes, "~\1", re.sub(re_prefix, '', kernel, count=1))
        cmp_str = "gt"
        if left.endswith(".old") and not right.endswith(".old"):
            left = left[:-4]
        if right.endswith(".old") and not left.endswith(".old"):
            right = right[:-4]
            cmp_str = "ge"
        if subprocess.call(["dpkg", "--compare-versions", left, cmp_str, right]) == 0:
            latest_kernel = kernel

    # This will likely output a path that considers the boot partition as /
    # e.g. /vmlinuz-4.4.44-1-pve
    booted_kernel = to_text(subprocess.check_output(["grep", "-o", "-P", "(?<=BOOT_IMAGE=).*?(?= )", "/proc/cmdline"]).strip())

    booted_kernel_package = ""
    old_kernel_packages = []

    if params['lookup_packages']:
        for kernel in kernels:
            if kernel.split("/")[-1] == booted_kernel.split("/")[-1]:
                booted_kernel_package = to_text(subprocess.check_output(["dpkg-query", "-S", kernel])).split(":")[0]
            elif kernel != latest_kernel:
                old_kernel_packages.append(to_text(subprocess.check_output(["dpkg-query", "-S", kernel])).split(":")[0])

    # returns True if we're not booted into the latest kernel
    new_kernel_exists = booted_kernel.split("/")[-1] != latest_kernel.split("/")[-1]
    module.exit_json(changed=False, new_kernel_exists=new_kernel_exists, old_packages=old_kernel_packages, booted_package=booted_kernel_package)

if __name__ == '__main__':
    main()
