#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import sys

def main():
    try:
        df = pd.read_csv("hw_results.csv")
    except FileNotFoundError:
        print("Error: hw_results.csv not found.")
        return

    # Filter/Clean data if needed
    print("\n--- Benchmark Summary ---")
    print(df.to_string(index=False))

    # Plot PPS
    plt.figure(figsize=(12, 7))
    colors = plt.cm.viridis(np.linspace(0, 1, len(df['mode'])))
    plt.bar(df['mode'], df['pps'], color=colors)
    plt.axhline(y=1488095, color='r', linestyle='--', label='1Gbps Line Rate (64B)')
    plt.ylabel('Packets Per Second (PPS)')
    plt.title('Drop Throughput: Baseline vs Netfilter vs XDP (Native)')
    plt.xticks(rotation=45)
    plt.legend()
    plt.tight_layout()
    plt.savefig('pps_comparison.png')

    # Plot SIQ
    plt.figure(figsize=(12, 7))
    plt.bar(df['mode'], df['siq'], color=colors)
    plt.ylabel('CPU SoftIRQ Utilization (%)')
    plt.title('CPU Overhead (SoftIRQ) Comparison')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('cpu_overhead.png')

    # Plot Latency (if exists in csv)
    if 'latency' in df.columns:
        plt.figure(figsize=(12, 7))
        plt.bar(df['mode'], df['latency'], color=colors)
        plt.ylabel('Latency (ms)')
        plt.title('Network Latency under Load')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('latency_comparison.png')

    print("\nGraphs saved: pps_comparison.png, cpu_overhead.png, latency_comparison.png")

if __name__ == "__main__":
    main()
