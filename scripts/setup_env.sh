#!/bin/bash

# Zatrzymanie skryptu w przypadku błędu
set -e

echo "🚀 Rozpoczynam konfigurację środowiska XDP-L2-Guard..."

# 1. Weryfikacja wersji jądra (wymagane 5.15+)
KERNEL_VERSION=$(uname -r)
echo "🛡️ Wykryta wersja jądra: $KERNEL_VERSION"

# 2. Aktualizacja repozytoriów i instalacja paczek bazowych
echo "📦 Instalowanie pakietów bazowych, kompilatorów i narzędzi BCC..."
# Wymagane narzędzia LLVM/Clang oraz nagłówki jądra do kompilacji "restrykcyjnego C" do eBPF bytecode
sudo apt update && sudo apt install -y \
    clang \
    llvm \
    libbpf-dev \
    linux-headers-$(uname -r) \
    python3-bpfcc \
    bpfcc-tools \
    python3-pyroute2 \
    ethtool \
    net-tools

# 3. Weryfikacja instalacji cgroup v2 (wymagane przez nowoczesne mapy eBPF)
if grep -q cgroup2 /proc/filesystems; then
    echo "✅ Wsparcie dla cgroup v2 zweryfikowane."
else
    echo "⚠️ UWAGA: Brak wsparcia cgroup v2, sprawdź konfigurację jądra!"
fi

# 4. Optymalizacja interfejsu pod XDP Native (Wyłączenie hardware offloading)
# Domyślnie bierzemy pierwszy aktywny interfejs (zazwyczaj eth0 lub enp0s3)
INTERFACE=$(ip route | grep default | sed -e "s/^.*dev.//" -e "s/.proto.*//")

echo "🔧 Konfiguracja interfejsu sieciowego: $INTERFACE"
echo "Wyłączanie funkcji GRO/GSO (Generic Receive Offload), aby zapobiec konfliktom segmentacji ramek..."
# Wyłączamy asystę hardware'u, przekierowując pakiety prosto na pętlę natywnego eBPF
sudo ethtool -K $INTERFACE gro off gso off tx off rx off || echo "Uwaga: Niektóre opcje ethtool mogą nie być wspierane przez wirtualną kartę."

echo "🎉 Środowisko gotowe! Możesz teraz uruchomić skrypty ładujące w przestrzeni użytkownika."