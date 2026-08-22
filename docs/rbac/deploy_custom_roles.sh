#!/usr/bin/env bash
#
# Deploy / update the ACRME custom RBAC roles.
#
# Prereqs:
#   - Azure CLI logged in (az login) with an identity holding
#     Microsoft.Authorization/roleDefinitions/write at the target scope
#     (Owner or User Access Administrator on the assignable scopes).
#   - Replace the <PLACEHOLDER> tokens in each custom_roles/*.json first,
#     or export the env vars below and let this script substitute them.
#
# Usage:
#   export PROVIDER_SUBSCRIPTION_ID="00000000-..."
#   export CONSUMER_SUBSCRIPTION_ID="11111111-..."
#   export PROVIDER_CRG_RG="rg-acrme-crg-prod"
#   export CONSUMER_VM_RG="rg-consumer-workload"
#   ./deploy_custom_roles.sh            # create/update all roles
#   ./deploy_custom_roles.sh --dry-run  # print the resolved JSON only
#
set -euo pipefail

DRY_RUN="false"
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN="true"

ROLE_DIR="$(cd "$(dirname "$0")/custom_roles" && pwd)"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

: "${PROVIDER_SUBSCRIPTION_ID:?set PROVIDER_SUBSCRIPTION_ID}"
: "${CONSUMER_SUBSCRIPTION_ID:=$PROVIDER_SUBSCRIPTION_ID}"
: "${PROVIDER_CRG_RG:=rg-acrme-crg}"
: "${CONSUMER_VM_RG:=rg-consumer-workload}"

echo "Provider sub : $PROVIDER_SUBSCRIPTION_ID"
echo "Consumer sub : $CONSUMER_SUBSCRIPTION_ID"
echo "Provider RG  : $PROVIDER_CRG_RG"
echo "Consumer RG  : $CONSUMER_VM_RG"
echo "Dry run      : $DRY_RUN"
echo

for src in "$ROLE_DIR"/*.json; do
  name="$(basename "$src")"
  out="$TMP_DIR/$name"
  sed -e "s|<PROVIDER_SUBSCRIPTION_ID>|$PROVIDER_SUBSCRIPTION_ID|g" \
      -e "s|<CONSUMER_SUBSCRIPTION_ID>|$CONSUMER_SUBSCRIPTION_ID|g" \
      -e "s|<PROVIDER_CRG_RG>|$PROVIDER_CRG_RG|g" \
      -e "s|<CONSUMER_VM_RG>|$CONSUMER_VM_RG|g" \
      "$src" > "$out"

  role_name="$(python3 -c "import json,sys; print(json.load(open('$out'))['Name'])")"

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "----- $role_name (resolved) -----"
    cat "$out"; echo
    continue
  fi

  if az role definition list --name "$role_name" --query "[0].roleName" -o tsv 2>/dev/null | grep -q .; then
    echo "Updating existing role: $role_name"
    az role definition update --role-definition "$out" 1>/dev/null
  else
    echo "Creating role: $role_name"
    az role definition create --role-definition "$out" 1>/dev/null
  fi
  echo "  done: $role_name"
done

echo
echo "All ACRME custom roles processed."
echo "NEXT: assign each role to its UAMI at the NARROWEST scope. See deploy_role_assignments.sh"
