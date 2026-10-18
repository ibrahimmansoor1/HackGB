"""One-time setup: print a new Nostr key pair for the Rehome storefront.

    python scripts/nostr_keygen.py

Put the nsec in .env as NOSTR_NSEC (never commit it). The npub is public:
your listings show at https://shopstr.store/marketplace/<npub>.
"""
from nostr_sdk import Keys

keys = Keys.generate()
npub = keys.public_key().to_bech32()
print(f"NOSTR_NSEC={keys.secret_key().to_bech32()}")
print(f"npub:      {npub}")
print(f"storefront: https://shopstr.store/marketplace/{npub}")
