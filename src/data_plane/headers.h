#ifndef __HEADERS_H
#define __HEADERS_H

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>

/* * Makro pomocnicze do weryfikacji barier pamięciowych (Bounds Checking).
 * Wymagane bezwzględnie przez eBPF Verifier przed próbą dostępu do nagłówka.
 * Eliminuje błędy typu "invalid stack" oraz "!read_ok".
 */
#define BOUNDS_CHECK(pointer, type, data_end) \
    do { \
        if ((void *)(pointer) + sizeof(type) > (void *)(data_end)) \
            return XDP_PASS; \
    } while(0)

#endif // __HEADERS_H