#include "headers.h"

// Native CO-RE BTF map definition (Kernel 5.15+)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __type(key, __u32);   // Key: IPv4 source address (32-bit)
    __type(value, __u64); // Value: Dropped frame counter
    __uint(max_entries, 100000);
} blacklist_ips SEC(".maps");

// Section name set to standard "xdp" supported natively by iproute2
SEC("xdp")

int xdp_drop_logic(struct xdp_md *ctx) {
    // 1. Extract pointers from the DMA layer context
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    
    // 2. Strict Bounds Checking
    BOUNDS_CHECK(eth, struct ethhdr, data_end);

    // Filter traffic using CO-RE bpf_htons()
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(struct ethhdr);
    BOUNDS_CHECK(ip, struct iphdr, data_end);

    __u32 src_ip = ip->saddr;

    // 3. Lookup in the native BPF API
    __u64 *drop_cnt = bpf_map_lookup_elem(&blacklist_ips, &src_ip);

    if (drop_cnt) {
        // Atomic statistics increment
        __sync_fetch_and_add(drop_cnt, 1);
        return XDP_DROP;
    }

    return XDP_PASS;
}

/*
int xdp_panic_test(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    struct ethhdr *eth = data;
    
    // ⚠️ INTENTIONAL ENGINEERING ERROR ⚠️
    // We deliberately removed the BOUNDS_CHECK macro!
    // We are attempting to read a structure field (eth->h_proto) from RAM 
    // without first verifying if the packet is large enough.
    // In a traditional kernel module (C), this could cause a Kernel Panic (Out-Of-Bounds Read).
    
    if (eth->h_proto == bpf_htons(ETH_P_IP)) {
        return XDP_DROP;
    }
    
    return XDP_PASS;
}
*/
char _license[] SEC("license") = "GPL";