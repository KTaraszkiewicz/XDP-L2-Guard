#include "headers.h"

// Inicjalizacja nowoczesnej mapy eBPF za pomocą BTF (Kernel 5.15+)
struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __type(key, __u32);   // Klucz: Adres źródłowy IPv4 (32-bit)
    __type(value, __u64); // Wartość: Licznik zrzuconych ram
    __uint(max_entries, 100000);
} blacklist_ips SEC(".maps");

SEC("xdp_prog")
int xdp_drop_logic(struct xdp_md *ctx) {
    // 1. Ekstrakcja wskaźników z kontekstu bezpośrednio od warstwy DMA
    void *data = (void *)(long)ctx->data;
    void *data_end = (void *)(long)ctx->data_end;

    // Rzutowanie na nagłówek ramki Ethernet
    struct ethhdr *eth = data;
    
    // 2. Rygorystyczny Bounds Checking (użycie makra z headers.h)
    BOUNDS_CHECK(eth, struct ethhdr, data_end);

    // Przesiewamy ruch, wpuszczając do głębszej weryfikacji tylko pakiety IPv4
    if (eth->h_proto != __constant_htons(ETH_P_IP))
        return XDP_PASS;

    // Przesunięcie wskaźnika na początek nagłówka IP
    struct iphdr *ip = data + sizeof(struct ethhdr);

    // Weryfikacja barier dla struktury IP
    BOUNDS_CHECK(ip, struct iphdr, data_end);

    __u32 src_ip = ip->saddr;

    // 3. Sprawdzenie w stałym czasie O(1), czy adres figuruje na czarnej liście
    __u64 *drop_cnt = bpf_map_lookup_elem(&blacklist_ips, &src_ip);

    if (drop_cnt) {
        // Atomowa inkrementacja statystyk w mapie współdzielonej
        __sync_fetch_and_add(drop_cnt, 1);
        
        // Zjawisko DROP: Bezwarunkowe zniszczenie ramy tuż przed stosowaniem sk_buff
        return XDP_DROP;
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";