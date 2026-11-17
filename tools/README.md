# Repository tools

## Recover GitHub CLI authentication

Run this helper when GitHub CLI credentials expire or the wrong account is active:

```bash
./tools/reauthenticate_github.sh
```

Requires Bash and [GitHub CLI](https://cli.github.com/). Run from the repository
root in an interactive terminal. By default it selects `vishnu4573` and verifies
write access to `vishnu4573/acrme-capacity-reservation`. If stored credentials
cannot be selected or verified, it starts browser sign-in, selects the requested
account again, and checks access. Complete browser sign-in with that account and
authorize SSO if required.

Check the current identity and access without switching accounts or signing in:

```bash
./tools/reauthenticate_github.sh --check
```

Force browser reauthentication, or specify another account and repository:

```bash
./tools/reauthenticate_github.sh --reauth
./tools/reauthenticate_github.sh ACCOUNT OWNER/REPOSITORY
```

The script does not read, print, or store token values; GitHub CLI manages its
credentials. It refuses to proceed when `GH_TOKEN` or `GITHUB_TOKEN` overrides
stored credentials. Remove an unintended override from your shell or credential
source before retrying; for a temporary shell override:

```bash
unset GH_TOKEN GITHUB_TOKEN
```

Do not remove deliberately configured CI credentials. This helper is for
interactive local use, not unattended pipelines.

Failed authentication, missing write access, or API/network errors return a
nonzero exit status. Reauthentication cannot grant repository permissions or
bypass Enterprise Managed User restrictions, organization policies, required
reviews, checks, or branch protection. An API failure can also indicate a network
problem; browser sign-in will not fix an outage.

The helper changes GitHub CLI's active account when recovering access, but does
not modify Git remotes, SSH keys, or Git credential-helper configuration. Success
verifies identity and repository write permission, not an actual PR creation,
merge, or Git push.

### Tests

The tests use a fake `gh` executable and never authenticate or contact GitHub:

```bash
python3 -m unittest discover -s tools -p 'test_*.py'
```
