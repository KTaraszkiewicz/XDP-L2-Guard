#ifndef __HEADERS_H
#define __HEADERS_H

#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/in.h>
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_endian.h>

// Minimal ICMP header to avoid toolchain issues
struct icmphdr {
  __u8		type;
  __u8		code;
  __sum16	checksum;
  union {
	struct {
		__be16	id;
		__be16	sequence;
	} echo;
	__be32	gateway;
	struct {
		__be16	__unused;
		__be16	mtu;
	} frag;
	__u8	reserved[4];
  } un;
};

#define ICMP_ECHO		8
#define ICMP_ECHOREPLY		0

/* * Helper macro for memory boundary verification (Bounds Checking).
 * Ensures safe packet parsing and satisfies the eBPF Verifier requirements.
 */
#define BOUNDS_CHECK(pointer, type, data_end) \
    do { \
        if ((void *)(pointer) + sizeof(type) > (void *)(data_end)) \
            return XDP_PASS; \
    } while(0)

#endif // __HEADERS_H