## Inicjalizacja Środowiska i Kronika Wykonanych Czynności Wdrożeniowych

Pomyślna implementacja systemu wczesnego zrzutu pakietów `XDP-L2-Guard` wymagała ścisłej korelacji pomiędzy konfiguracją fizycznego (lub parawirtualizowanego) sprzętu a podsystemami jądra Linux. Poniższy rozdział stanowi chronologiczny i techniczny opis działań podjętych w celu przygotowania stabilnego, izolowanego środowiska laboratoryjnego, zdolnego do obsługi natywnego trybu przetwarzania danych (XDP Native Mode) przy zachowaniu pełnej zgodności z restrykcjami eBPF Verifiera.

### 1. Konfiguracja Warstwy Hiperwizora (VirtualBox Settings)

W celu przeprowadzenia miarodajnych testów porównawczych z tradycyjnymi mechanizmami Netfilter (iptables), środowisko uruchomieniowe zostało oparte na architekturze maszyn wirtualnych z precyzyjnie zdefiniowaną topologią sieciową. W fazie wstępnej wykonano następujące kroki konfiguracyjne z poziomu menedżera hiperwizora:

**Alokacja Zasobów Obliczeniowych:** Maszynie wirtualnej przydzielono 4 rdzenie procesora hosta oraz 16 GB pamięci RAM, co stanowi polecane wartości dla stabilnego działania kompilacji JIT oraz pochłaniania masowych strumieni pakietów generowanych podczas symulacji ataków DDoS.  
**Implementacja Parawirtualizowanego vNIC:** W sekcji ustawień sieciowych kontrolera zmieniono domyślny typ karty na sterownik parawirtualizowany  
**Paravirtualized Network (virtio-net)**. Czynność ta była krytyczna – architektura XDP w trybie Native (`xdpdrv`) wymaga bezpośredniego wsparcia programistycznego wewnątrz kodu źródłowego sterownika danej karty sieciowej, a `virtio_net` (podobnie jak pary interfejsów `veth`) posiada natywne punkty zaczepienia (hooks) dla eBPF.  
**Aktywacja Trybu Promiscuous:** Flagę trybu nasłuchiwania wirtualnego interfejsu przestawiono w stan *Allow All* (Pozwól wszystkim), eliminując odrzucanie ramek na poziomie sprzętowym karty i wymuszając ich bezwarunkowe przekazywanie do kolejki odbiorczej (Rx Ring Buffer) interfejsu sieciowego hosta.  

### 2. Prowizjonowanie Środowiska i Instalacja Kompilatorów (Post-Boot)

Po uruchomieniu czystej instancji systemu operacyjnego Ubuntu 22.04 LTS (wybranego ze względu na obecność nowoczesnego jądra w gałęzi 5.15+ spełniającego rygorystyczne kryteria weryfikatora BPF), proces instalacji zależności został w pełni zautomatyzowany poprzez autorski skrypt narzędziowy `setup_env.sh`. Skrypt wykonał w przestrzeni użytkownika następujące operacje niskopoziomowe:

**Aktualizacja Indeksów Menedżera Pakietów:** Przeprowadzono pełną synchronizację repozytoriów za pomocą komendy `sudo apt update`.  
**Wdrożenie Toolchainu Kompilacyjnego LLVM/Clang:** Zainstalowano pakiety `clang` oraz `llvm`, niezbędne do transformacji restrykcyjnego kodu źródłowego C (Data Plane) w uniwersalny kod bajtowy eBPF (eBPF bytecode).  
**Instalacja Nagłówków Jądra:** Dołączono pakiet `linux-headers-$(uname -r)`, dostarczający aktualne definicje struktur pamięciowych jądra, co pozwala programowi XDP na bezpieczną interpretację pól nagłówkowych surowej ramki L2/L3.  
**Instalacja Bibliotek Środowiska Uruchomieniowego:** Zainstalowano framework BCC (BPF Compiler Collection) wraz z `libbpf-dev` i `python3-bcc`, zapewniając kompletne API dla skryptu ładującego (Control Plane) w języku Python. Biblioteki te ukrywają skomplikowane wywołania systemowe `bpf()` i odpowiadają za kompilację Just-In-Time (JIT) kodu C w pamięci jądra.  

### 3. Mitygacja Anomalii Segmentacji Ramek (Modyfikacja ethtool)

Najpoważniejszym wyzwaniem inżynieryjnym na etapie konfiguracji interfejsów było zjawisko automatycznego, sprzętowego odciążania procesora przez wirtualne karty sieciowe (GRO/CSUM Anomalies). Podczas pierwszych prób montowania kodu jądro systemowe zgłaszało błąd niekompatybilności i degradowało środowisko do emulowanego, wolniejszego trybu Generic (`xdpgeneric`), drastycznie zwiększając narzut procesora.

Powodem był aktywny mechanizm Generic Receive Offload (GRO), który scalał przychodzące ramki w gigantyczne pakiety przed ich przekazaniem do systemu, co łamało limity pamięciowe eBPF (restrykcja alokacji do wielkości mniejszej niż pojedyncza strona pamięci – Page Size, poniżej ~3KB ramy). 

Aby wyeliminować tę barierę architektoniczną i wymusić działanie programu bezpośrednio na surowych danych w buforze DMA sterownika, podjęto następujące akcje:
**Manualna Blokada Offloadingu:** Wykonano restrykcyjne polecenie rekonfiguracji interfejsu przy użyciu narzędzia diagnostycznego: `sudo ethtool -K eth0 gro off gso off tx off rx off`.  
**Rezultat Operacji:** Odłączenie asysty sprzętowej przywróciło dostarczanie niezmienionych, surowych ramek o standardowym rozmiarze MTU bezpośrednio do linii NAPI sterownika. Umożliwiło to pomyślne podpięcie hooka `XDP Native` bez ryzyka fragmentacji danych i zapewniło optymalne warunki do przeprowadzenia testów stresowych systemu bezpieczeństwa.  