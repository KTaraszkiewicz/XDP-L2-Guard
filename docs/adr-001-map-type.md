# ADR 1: Choice of BPF Map Type for IP Filtering

## Status
Accepted

## Context
XDP-L2-Guard needs to store filtering rules that map a destination IP address to a specific action (DROP, PASS, NAT, etc.). We need to decide which BPF map type is most suitable for this purpose.

The primary candidates are:
1. `BPF_MAP_TYPE_HASH`: Optimized for exact matches.
2. `BPF_MAP_TYPE_LPM_TRIE`: Optimized for longest prefix matches (subnet-based filtering).

## Decision
We chose `BPF_MAP_TYPE_HASH` for the initial implementation.

## Consequences
- **Pros**:
    - Faster lookups for exact IP matches ($O(1)$ average case).
    - Simpler implementation in both kernel and user space.
    - Sufficient for the current project requirements (filtering specific target hosts).
- **Cons**:
    - Does not support subnet-based filtering (e.g., blocking `192.168.1.0/24`).
    - Adding support for subnets in the future would require switching to `LPM_TRIE` or implementing a custom matching logic.

## Future Considerations
If the requirement evolves to support CIDR-based blocking, we should migrate the `action_map` to `BPF_MAP_TYPE_LPM_TRIE`.
