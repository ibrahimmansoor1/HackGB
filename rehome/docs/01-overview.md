# 01 · Overview

## Problem

A large share of usable clothing and household goods ends up in landfills. The main reason isn't that nobody wants them; it's friction. Selling or donating properly means photographing, describing, listing, answering messages, and driving somewhere. Most people don't have the time.

The other side has friction too. People who need things (and the organizations serving them) have to hunt through thrift stores and marketplaces with no guarantee of finding the right item.

> TODO (presentation owner): add 2–3 sourced statistics on textile and household waste for the opening slide.

## Solution

Two entry points and a team of AI agents in between.

- **Donors** take a photo or type a short description. Agents identify the item, write a structured listing, and store it. *(Stretch: list it for sale on Nostr, where it shows on Shopstr; if unsold after 30 days, release it to the donation pool. eBay/Etsy/Shopify are roadmap.)*
- **Requesters** describe what they need in plain language. Agents infer the context (Chicago in December means insulated and waterproof), search the inventory by similarity, and return ranked matches with a reason for each.

## One-line pitch

One photo to give something away; one sentence to find what you need. Agents handle everything in between.

## What makes it technically interesting

- **Multimodal input:** vision model turns a photo into structured data.
- **Multi-agent orchestration:** orchestrator delegates to specialized parser and requester agents.
- **Contextual matching:** the requester agent expands vague intent into concrete requirements before a vector similarity search.
- **Visible reasoning:** a live activity feed shows each agent step during the demo.
