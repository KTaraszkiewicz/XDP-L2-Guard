# Developer Guide

This guide is intended for developers who wish to modify or extend XDP-L2-Guard.

## Development Environment

The project is optimized for Ubuntu 22.04 LTS. Ensure you have the necessary dependencies installed:

```bash
sudo ./scripts/setup_env.sh
```

## Compilation

The project uses a `Makefile` to compile the eBPF C code into an object file using `clang`.

```bash
make
```

This will generate `src/data_plane/filter.o`. The `Makefile` uses `bpftool` to generate `vmlinux.h` if needed, supporting the CO-RE (Compile Once - Run Everywhere) architecture.

## Adding New Actions

To add a new action (e.g., `LOGGING` or `RATE_LIMITING`):

1. **Update `src/data_plane/filter.c`**:
   - Add the new action to `enum xdp_action_target`.
   - Implement the logic inside the `switch (cfg->target)` block in `xdp_drop_logic`.
2. **Update Control Plane**:
   - Modify `src/control_plane/guard.py` to support the new target in the CLI.
   - If using the bash wrapper, update `scripts/guard.sh`.

## Testing & Validation

Several scripts are provided in the `scripts/` directory for testing:

### Simple Ping Test
Located in `scripts/simple_ping/`, this set of scripts sets up a test environment using network namespaces.
- `setup.sh`: Creates namespaces and virtual ethernet pairs.
- `ping.sh`: Runs a ping test between namespaces.
- `block.sh` / `unblock.sh`: Demonstrates adding/removing drop rules.

### Action Showcase
Located in `scripts/action_showcase/`, these scripts demonstrate advanced actions like `REDIRECT` and `NAT`.
- `setup.sh`: Sets up a complex topology with multiple namespaces.
- `monitor.sh`: Runs `tcpdump` in background namespaces to verify packet arrival.

### Performance Testing
`scripts/pktgen_flood/pktgen_flood.sh` can be used to generate high volumes of UDP traffic to test the filter's performance under load.

## Debugging

Since eBPF runs in the kernel, debugging is primarily done via `bpf_printk`. You can view the output using:

```bash
sudo cat /sys/kernel/debug/tracing/trace_pipe
```

Alternatively, use `bpftool` to inspect maps:

```bash
sudo bpftool map dump name action_map
```
