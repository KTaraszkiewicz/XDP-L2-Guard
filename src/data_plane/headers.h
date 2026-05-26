#ifndef __HEADERS_H
#define __HEADERS_H

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

/* * Helper macro for memory boundary verification (Bounds Checking).
 * Ensures safe packet parsing and satisfies the eBPF Verifier requirements.
 */
#define BOUNDS_CHECK(pointer, type, data_end) \
    do { \
        if ((void *)(pointer) + sizeof(type) > (void *)(data_end)) \
            return XDP_PASS; \
    } while(0)

#endif // __HEADERS_H