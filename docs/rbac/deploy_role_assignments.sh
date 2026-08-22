#!/usr/bin/env bash
#
# Assign the ACRME custom roles to their User-Assigned Managed Identities
# at the NARROWEST feasible scope. Run AFTER deploy_custom_roles.sh.
#
# This is a REFERENCE script. Review every scope before running in production.
# The Consumer Compute assignment is intentionally COMMENTED OUT — it is the
# G-14 Tier 3 role and must only be assigned per incident, with a recorded
# consent artifact and a tested revocation procedure.
#
# Required object IDs (principalId of each UAMI):
#   READER_MI_OID, CAPACITY_MI_OID, SHARING_MI_OID, QUOTA_MI_OID, CONSUMER_MI_OID
#
set -euo pipefail

: "${PROVIDER_SUBSCRIPTION_ID:?set PROVIDER_SUBSCRIPTION_ID}"
: "${CONSUMER_SUBSCRIPTION_ID:=$PROVIDER_SUBSCRIPTION_ID}"
: "${PROVIDER_CRG_RG:=rg-acrme-crg}"
: "${CONSUMER_VM_RG:=rg-consumer-workload}"

: "${READER_MI_OID:?set READER_MI_OID}"
: "${CAPACITY_MI_OID:?set CAPACITY_MI_OID}"
: "${SHARING_MI_OID:?set SHARING_MI_OID}"
: "${QUOTA_MI_OID:?set QUOTA_MI_OID}"

PROV_SUB="/subscriptions/$PROVIDER_SUBSCRIPTION_ID"
CONS_SUB="/subscriptions/$CONSUMER_SUBSCRIPTION_ID"
PROV_RG="$PROV_SUB/resourceGroups/$PROVIDER_CRG_RG"

echo "==> ACRME Reader (read-only, both subscriptions)"
az role assignment create --assignee-object-id "$READER_MI_OID" --assignee-principal-type ServicePrincipal \
  --role "ACRME Reader" --scope "$PROV_SUB"
az role assignment create --assignee-object-id "$READER_MI_OID" --assignee-principal-type ServicePrincipal \
  --role "ACRME Reader" --scope "$CONS_SUB"

echo "==> ACRME Capacity Operator (provider CRG resource group ONLY)"
az role assignment create --assignee-object-id "$CAPACITY_MI_OID" --assignee-principal-type ServicePrincipal \
  --role "ACRME Capacity Operator" --scope "$PROV_RG"

echo "==> ACRME Sharing Operator (provider CRG resource group ONLY)"
az role assignment create --assignee-object-id "$SHARING_MI_OID" --assignee-principal-type ServicePrincipal \
  --role "ACRME Sharing Operator" --scope "$PROV_RG"

echo "==> ACRME Quota Operator (provider subscription)"
az role assignment create --assignee-object-id "$QUOTA_MI_OID" --assignee-principal-type ServicePrincipal \
  --role "ACRME Quota Operator" --scope "$PROV_SUB"

# ---------------------------------------------------------------------------
# G-14 TIER 3 — DISABLED BY DEFAULT. Do NOT uncomment for standing access.
# Assign per incident to the consumer VM resource group, then REVOKE after.
# ---------------------------------------------------------------------------
# : "${CONSUMER_MI_OID:?set CONSUMER_MI_OID}"
# CONS_RG="$CONS_SUB/resourceGroups/$CONSUMER_VM_RG"
# az role assignment create --assignee-object-id "$CONSUMER_MI_OID" --assignee-principal-type ServicePrincipal \
#   --role "ACRME Consumer Compute Operator" --scope "$CONS_RG"
#
# REVOCATION (run immediately after the Tier 3 operation completes):
# az role assignment delete --assignee-object-id "$CONSUMER_MI_OID" \
#   --role "ACRME Consumer Compute Operator" --scope "$CONS_RG"

echo
echo "Standing assignments complete. Tier 3 consumer role remains unassigned (G-14)."
