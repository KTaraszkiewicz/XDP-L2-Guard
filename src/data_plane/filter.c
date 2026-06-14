#include "headers.h"

// Action targets enum
enum xdp_action_target {
    ACTION_PASS = 0,
    ACTION_DROP,
    ACTION_TX,
    ACTION_REDIRECT,
    ACTION_NAT
};

struct action_cfg {
    __u32 target;
    __u32 new_ip;
    __u32 ifindex;
    __u64 dropped_packets;
};

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __type(key, __u32);
    __type(value, struct action_cfg);
    __uint(max_entries, 10000);
} action_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_DEVMAP);
    __uint(key_size, sizeof(__u32));
    __uint(value_size, sizeof(__u32));
    __uint(max_entries, 256);
} dev_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __type(key, __u32);
    __type(value, __u64);
    __uint(max_entries, 1);
} total_dropped SEC(".maps");

static __always_inline void swap_mac(struct ethhdr *eth) {
    __u8 tmp[ETH_ALEN];
    __builtin_memcpy(tmp, eth->h_source, ETH_ALEN);
    __builtin_memcpy(eth->h_source, eth->h_dest, ETH_ALEN);
    __builtin_memcpy(eth->h_dest, tmp, ETH_ALEN);
}

static __always_inline void swap_ip(struct iphdr *ip) {
    __u32 tmp = ip->saddr;
    ip->saddr = ip->daddr;
    ip->daddr = tmp;
}

SEC("xdp")
int xdp_drop_logic(struct xdp_md *ctx) {
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    BOUNDS_CHECK(eth, struct ethhdr, data_end);

    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(struct ethhdr);
    BOUNDS_CHECK(ip, struct iphdr, data_end);

    __u32 dst_ip = bpf_ntohl(ip->daddr);
    struct action_cfg *cfg = bpf_map_lookup_elem(&action_map, &dst_ip);
    
    bpf_printk("XDP: lookup ip=%pI4 hex=%x cfg=%p", &dst_ip, dst_ip, cfg);

    if (!cfg) {
        return XDP_PASS;
    }

    switch (cfg->target) {
        case ACTION_DROP: {
            __u32 key = 0;
            __u64 *val = bpf_map_lookup_elem(&total_dropped, &key);
            if (val) __sync_fetch_and_add(val, 1);
            __sync_fetch_and_add(&cfg->dropped_packets, 1);
            return XDP_DROP;
        }

        case ACTION_TX: {
            if (ip->protocol == IPPROTO_ICMP) {
                struct icmphdr *icmp = (void *)ip + sizeof(struct iphdr);
                BOUNDS_CHECK(icmp, struct icmphdr, data_end);

                if (icmp->type == ICMP_ECHO) {
                    // 1. Change to Reply
                    icmp->type = ICMP_ECHOREPLY;
                    
                    // 2. Fix ICMP Checksum (Type 8 -> 0 is -0x0800 in sum)
                    // We add 0x0800 to the 1's complement checksum
                    __u32 temp_csum = bpf_ntohs(icmp->checksum);
                    temp_csum += 0x0800;
                    if (temp_csum > 0xFFFF) temp_csum -= 0xFFFF;
                    icmp->checksum = bpf_htons(temp_csum);

                    // 3. Swap and Send
                    swap_mac(eth);
                    swap_ip(ip);
                    return XDP_TX;
                }
            }
            return XDP_PASS;
        }

        case ACTION_REDIRECT: {
            // If new_ip is set, perform DNAT before redirecting
            if (cfg->new_ip) {
                __u32 old_daddr = ip->daddr;
                __u32 new_daddr = cfg->new_ip;
                
                __u32 csum = ~bpf_ntohs(ip->check) & 0xFFFF;
                csum += (~(old_daddr & 0xFFFF) & 0xFFFF) + (new_daddr & 0xFFFF);
                csum += (~(old_daddr >> 16) & 0xFFFF) + (new_daddr >> 16);
                while (csum >> 16) csum = (csum & 0xFFFF) + (csum >> 16);
                ip->check = bpf_htons(~csum & 0xFFFF);
                
                ip->daddr = new_daddr;
            }

            int err = bpf_redirect_map(&dev_map, cfg->ifindex, 0);
            bpf_printk("XDP: redirect dnat=%pI4 ifindex=%u res=%d", &cfg->new_ip, cfg->ifindex, err);
            return err;
        }

        case ACTION_NAT: {
            // Simple DNAT (Destination IP change)
            // Fix IP Checksum (Incremental)
            __u32 old_daddr = ip->daddr;
            __u32 new_daddr = cfg->new_ip;
            
            __u32 csum = ~bpf_ntohs(ip->check) & 0xFFFF;
            // Subtract old, add new (using 16-bit halves)
            csum += (~(old_daddr & 0xFFFF) & 0xFFFF) + (new_daddr & 0xFFFF);
            csum += (~(old_daddr >> 16) & 0xFFFF) + (new_daddr >> 16);
            while (csum >> 16) csum = (csum & 0xFFFF) + (csum >> 16);
            ip->check = bpf_htons(~csum & 0xFFFF);
            
            ip->daddr = new_daddr;
            return XDP_PASS;
        }

        case ACTION_PASS:
        default:
            return XDP_PASS;
    }
}

char _license[] SEC("license") = "GPL";
