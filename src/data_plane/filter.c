#include "headers.h"

// Natywna definicja mapy CO-RE BTF (Kernel 5.15+)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __type(key, __u32);   // Klucz: Adres źródłowy IPv4 (32-bit)
    __type(value, __u64); // Wartość: Licznik zrzuconych ram
    __uint(max_entries, 100000);
} blacklist_ips SEC(".maps");

// Zmieniono nazwę sekcji na standardowe "xdp" obsługiwane domyślnie przez iproute2
SEC("xdp")
int xdp_drop_logic(struct xdp_md *ctx) {
    // 1. Ekstrakcja wskaźników z kontekstu warstwy DMA
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    struct ethhdr *eth = data;
    
    // 2. Rygorystyczny Bounds Checking 
    BOUNDS_CHECK(eth, struct ethhdr, data_end);

    // Przesiewamy ruch używając CO-RE bpf_htons()
    if (eth->h_proto != bpf_htons(ETH_P_IP))
        return XDP_PASS;

    struct iphdr *ip = data + sizeof(struct ethhdr);
    BOUNDS_CHECK(ip, struct iphdr, data_end);

    __u32 src_ip = ip->saddr;

    // 3. Sprawdzenie w natywnym API bpf_helpers
    __u64 *drop_cnt = bpf_map_lookup_elem(&blacklist_ips, &src_ip);

    if (drop_cnt) {
        // Atomowa inkrementacja statystyk
        __sync_fetch_and_add(drop_cnt, 1);
        return XDP_DROP;
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";