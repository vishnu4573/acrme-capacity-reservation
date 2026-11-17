#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'Usage: %s [--check | --reauth] [account [owner/repository]]\n' "$0"
    printf 'Defaults: vishnu4573 vishnu4573/acrme-capacity-reservation\n'
}

mode=auto
case "${1:-}" in
    --help|-h) usage; exit 0 ;;
    --check) mode=check; shift ;;
    --reauth) mode=reauth; shift ;;
esac
if [[ $# -gt 2 || "${1:-}" == -* ]]; then
    usage >&2
    exit 2
fi

account=${1:-vishnu4573}
repository=${2:-vishnu4573/acrme-capacity-reservation}

if ! command -v gh >/dev/null 2>&1; then
    printf 'GitHub CLI (gh) is required. Install it from https://cli.github.com/ and retry.\n' >&2
    exit 127
fi

if [[ -n "${GH_TOKEN:-}" || -n "${GITHUB_TOKEN:-}" ]]; then
    printf 'GH_TOKEN or GITHUB_TOKEN overrides stored credentials. Remove the override in your shell or its credential source, then retry. No token was changed.\n' >&2
    exit 1
fi

verify_access() {
    local login can_push
    if ! login=$(gh api --hostname github.com user --jq '.login'); then
        printf 'Unable to verify GitHub identity; authentication or network access failed.\n' >&2
        return 1
    fi
    if [[ "$login" != "$account" ]]; then
        printf 'Expected account %s, but GitHub authenticated as %s.\n' "$account" "$login" >&2
        return 1
    fi
    if ! can_push=$(gh api --hostname github.com "repos/$repository" --jq '.permissions.push'); then
        printf 'Unable to access repository %s as %s.\n' "$repository" "$account" >&2
        return 1
    fi
    if [[ "$can_push" != true ]]; then
        printf 'Account %s does not have repository write access to %s. Sign-in alone cannot grant access; contact the repository owner or use an authorized account.\n' "$account" "$repository" >&2
        return 1
    fi
    printf 'Verified: %s has write access to %s.\n' "$account" "$repository"
    printf 'PR creation and merging remain subject to organization policies, required reviews, checks, and branch rules.\n'
}

if [[ "$mode" == check ]]; then
    verify_access
    exit 0
fi

if [[ "$mode" == auto ]]; then
    if gh auth switch --hostname github.com --user "$account"; then
        if verify_access; then
            exit 0
        fi
    else
        printf 'Could not select stored credentials for %s; browser sign-in is required.\n' "$account" >&2
    fi
fi

printf 'Opening GitHub browser sign-in. Select account %s; complete any required SSO authorization.\n' "$account"
if ! gh auth login --hostname github.com --web; then
    printf 'GitHub sign-in failed or was cancelled. Retry when ready.\n' >&2
    exit 1
fi
if ! gh auth switch --hostname github.com --user "$account"; then
    printf 'Could not select %s after sign-in. Retry and sign in with the intended account.\n' "$account" >&2
    exit 1
fi
verify_access
