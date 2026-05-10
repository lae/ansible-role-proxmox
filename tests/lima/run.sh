#!/usr/bin/env bash
# Copyright (C) 2025-2026 lae
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Affero General Public License as published by the Free
# Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU Affero General Public License for more
# details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#

set -euo pipefail

ROOT_DIR="$(git -C "$(dirname "${BASH_SOURCE[0]}")/../.." rev-parse --show-toplevel)"
TESTS_DIR="${ROOT_DIR}/tests/lima"
WORK_DIR="${LIMA_WORKDIR:-${TMPDIR:-/tmp}/ansible-role-proxmox-lima}"
ARTIFACTS_DIR="${WORK_DIR}/artifacts"
ROLES_DIR="${WORK_DIR}/roles"
COLLECTIONS_DIR="${WORK_DIR}/collections"
INVENTORY_PATH="${WORK_DIR}/inventory.ini"
ROLE_ARCHIVE_PATH="${WORK_DIR}/lae.proxmox.tar.gz"
LIMA_TEMPLATE="${TESTS_DIR}/pve-instance.yaml"
LIMA_USER_NAME="${LIMA_USER_NAME:-lima}"
LIMA_BOOT_DISK="${LIMA_BOOT_DISK:-8GiB}"
LIMA_EXTRA_DISK_SIZE="${LIMA_EXTRA_DISK_SIZE:-128MiB}"
GIT_HEAD="$(git -C "${ROOT_DIR}" rev-parse --short HEAD)"
INSTANCES_STRING="${LIMA_INSTANCES:-pve-1 pve-2 pve-3}"
read -r -a INSTANCES <<<"${INSTANCES_STRING}"

usage() {
  cat <<'EOF'
Usage: tests/lima/run.sh up|provision|test|collect-logs|destroy|ci
EOF
}

require_commands() {
  local description="$1"
  shift
  local missing=()
  local command
  for command in "$@"; do
    if ! command -v "${command}" >/dev/null 2>&1; then
      missing+=("${command}")
    fi
  done

  if ((${#missing[@]} > 0)); then
    printf 'Missing required command(s) for %s: %s\n' "${description}" "${missing[*]}" >&2
    exit 1
  fi
}

ensure_directories() {
  mkdir -p "${WORK_DIR}" "${ARTIFACTS_DIR}" "${ROLES_DIR}" "${COLLECTIONS_DIR}"
}

instance_exists() {
  local instance="$1"
  limactl list "${instance}" --format '{{.Name}}' 2>/dev/null | grep -qx "${instance}"
}

disk_exists() {
  local disk="$1"
  limactl disk list | awk 'NR > 1 { print $1 }' | grep -qx "${disk}"
}

create_disk_if_needed() {
  local disk="$1"
  if ! disk_exists "${disk}"; then
    limactl disk create "${disk}" --size "${LIMA_EXTRA_DISK_SIZE}"
  fi
}

start_instance() {
  local instance="$1"
  local data_disk_a="${instance}-ceph"
  local data_disk_b="${instance}-zfs"

  create_disk_if_needed "${data_disk_a}"
  create_disk_if_needed "${data_disk_b}"

  if instance_exists "${instance}"; then
    limactl start "${instance}"
    return
  fi

  limactl start \
    --name="${instance}" \
    --tty=false \
    --set=".disk = \"${LIMA_BOOT_DISK}\"" \
    --set=".additionalDisks = [\"${data_disk_a}\", \"${data_disk_b}\"]" \
    "${LIMA_TEMPLATE}"
}

generate_inventory() {
  local ssh_key
  ssh_key="${LIMA_HOME:-${HOME}/.lima}/_config/user"

  mkdir -p "${WORK_DIR}"
  cat >"${INVENTORY_PATH}" <<EOF
[all:vars]
ansible_ssh_private_key_file=${ssh_key}
ansible_ssh_common_args='-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'

[all]
EOF

  local instance ssh_address ssh_port status
  for instance in "${INSTANCES[@]}"; do
    read -r ssh_address ssh_port status < <(
      limactl list "${instance}" --format '{{.SSHAddress}} {{.SSHLocalPort}} {{.Status}}'
    )
    if [[ "${status}" != "Running" ]]; then
      printf 'Instance %s is not running (status=%s)\n' "${instance}" "${status}" >&2
      exit 1
    fi
    cat >>"${INVENTORY_PATH}" <<EOF
${instance} ansible_host=${ssh_address} ansible_port=${ssh_port} ansible_user=${LIMA_USER_NAME} ansible_ssh_user=${LIMA_USER_NAME} lima_instance=${instance}
EOF
  done
}

package_role() {
  rm -f "${ROLE_ARCHIVE_PATH}"
  git -C "${ROOT_DIR}" ls-files -z \
    | tar --directory="${ROOT_DIR}" --null --files-from=- -czf "${ROLE_ARCHIVE_PATH}"
}

install_ansible_dependencies() {
  rm -rf "${ROLES_DIR}" "${COLLECTIONS_DIR}"
  mkdir -p "${ROLES_DIR}" "${COLLECTIONS_DIR}"

  ansible-galaxy collection install \
    --force \
    --collections-path "${COLLECTIONS_DIR}" \
    ansible.utils \
    ansible.posix \
    community.general

  ansible-galaxy role install \
    --force \
    --roles-path "${ROLES_DIR}" \
    frzk.chrony

  ansible-galaxy role install \
    --force \
    --roles-path "${ROLES_DIR}" \
    "${ROLE_ARCHIVE_PATH},devel-${GIT_HEAD},lae.proxmox"
}

run_playbook() {
  local playbook="$1"
  ANSIBLE_CONFIG="${ROOT_DIR}/tests/ansible.cfg" \
  ANSIBLE_ROLES_PATH="${ROLES_DIR}" \
  ANSIBLE_COLLECTIONS_PATH="${COLLECTIONS_DIR}:${HOME}/.ansible/collections:/usr/share/ansible/collections" \
  ansible-playbook -i "${INVENTORY_PATH}" "${playbook}"
}

collect_logs() {
  mkdir -p "${ARTIFACTS_DIR}"
  limactl list --format yaml >"${ARTIFACTS_DIR}/limactl-list.yaml" || true

  local instance
  for instance in "${INSTANCES[@]}"; do
    limactl shell "${instance}" sudo cat /var/log/cloud-init-output.log \
      >"${ARTIFACTS_DIR}/${instance}-cloud-init-output.log" 2>/dev/null || true
    limactl shell "${instance}" sudo journalctl --no-pager -u pvedaemon.service \
      >"${ARTIFACTS_DIR}/${instance}-pvedaemon.log" 2>/dev/null || true
    limactl shell "${instance}" sudo journalctl --no-pager -u pve-cluster.service \
      >"${ARTIFACTS_DIR}/${instance}-pve-cluster.log" 2>/dev/null || true
    limactl shell "${instance}" sudo journalctl --no-pager -u pveproxy.service \
      >"${ARTIFACTS_DIR}/${instance}-pveproxy.log" 2>/dev/null || true
  done
}

up() {
  require_commands up git limactl
  ensure_directories

  local instance
  for instance in "${INSTANCES[@]}"; do
    start_instance "${instance}"
  done

  generate_inventory
}

provision() {
  require_commands provision ansible-galaxy ansible-playbook git limactl tar
  ensure_directories
  package_role
  install_ansible_dependencies
  generate_inventory
  run_playbook "${TESTS_DIR}/provision.yml"
}

test_suite() {
  require_commands test ansible-playbook limactl
  generate_inventory
  run_playbook "${ROOT_DIR}/tests/test.yml"
}

destroy() {
  local instance
  for instance in "${INSTANCES[@]}"; do
    if instance_exists "${instance}"; then
      limactl delete --force "${instance}" || true
    fi
  done

  local disk
  for instance in "${INSTANCES[@]}"; do
    for disk in "${instance}-ceph" "${instance}-zfs"; do
      if disk_exists "${disk}"; then
        limactl disk delete --force "${disk}" || true
      fi
    done
  done
}

ci() {
  trap 'status=$?; collect_logs; destroy; exit "${status}"' EXIT
  up
  provision
  test_suite
}

command="${1:-}"
case "${command}" in
  up)
    up
    ;;
  provision)
    provision
    ;;
  test)
    test_suite
    ;;
  collect-logs)
    collect_logs
    ;;
  destroy)
    destroy
    ;;
  ci)
    ci
    ;;
  *)
    usage >&2
    exit 1
    ;;
esac
