#!/bin/bash
# Helper functions used when generating GRUB config
. "/usr/share/grub/grub-mkconfig_lib"

# Collect valid kernels into an array
list=
for i in /boot/vmlinuz-* /vmlinuz-* /boot/kernel-* ; do
    if grub_file_is_not_garbage "$i" ; then list="$list $i" ; fi
done 

# Use helper function to find latest kernel
latest_kernel=$(version_find_latest $list)

# Find currently booted kernel from boot options
booted_kernel=$(grep -oP "(?<=BOOT_IMAGE=).*?(?= )" /proc/cmdline)

# Print out status message for kernel changes if any
printf "updated="
[ "$booted_kernel" == "$latest_kernel" ] && printf "false" || printf "true"
