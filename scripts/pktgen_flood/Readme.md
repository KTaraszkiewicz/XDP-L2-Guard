nstrukcja obsługi (Plik README.md)

# Generator Ruchu Pktgen (Stres-Testy dla XDP / iptables)

Skrypt służy do generowania maksymalnej liczby pakietów na sekundę (PPS - *Packets Per Second*) przy minimalnym rozmiarze ramki (64 bajty na warstwie fizycznej). Narzędzie służy do porównywania wydajności mechanizmów filtrowania pakietów (XDP vs nftables/iptables) w sieci lokalnej poprzez symulację rozproszonego ataku typu Flood.

## 🚀 Jak to działa?
1. **Pełna automatyzacja CPU:** Skrypt automatycznie wykrywa liczbę rdzeni logicznych (`nproc`) maszyny testowej i uruchamia dedykowany wątek kernel-space dla każdego rdzenia.
2. **Klonowanie SKB (`CLONE_SKB`):** Pakiety są klonowane bezpośrednio w pamięci jądra. Eliminuje to narzut związany z alokacją pamięci RAM, pozwalając na osiągnięcie sprzętowych limitów karty sieciowej (Line Rate).
3. **RSS / Multiqueue Friendly:** Skrypt losuje porty źródłowe UDP, dzięki czemu karta sieciowa komputera odbierającego (celu) rozdzieli ruch na wiele procesorów za pomocą technologii RSS.

## 📋 Wymagania wstępne
Przed uruchomieniem upewnij się, że w systemie załadowany jest moduł jądra `pktgen`:
```bash
sudo modprobe pktgen
```
Uwaga: Skrypt musi być uruchamiany z uprawnieniami root / sudo, ponieważ operuje bezpośrednio na strukturach /proc/net/pktgen/.

## 🛠️ Przygotowanie przed uruchomieniem (KRYTYCZNE)
Otwórz skrypt w edytorze tekstowym i w linii zawierającej zmienną DST_MAC wpisz fizyczny adres MAC komputera docelowego (celu):

```Bash
DST_MAC="XX:XX:XX:XX:XX:XX"  # <-- Podaj MAC adres karty komputera, który zalewasz ruchem
```
Dlaczego? Jeśli podasz zły adres MAC, przełącznik (switch) lub karta sieciowa celu odrzuci pakiety na poziomie sprzętowym. Wtedy programy XDP lub iptables na celu w ogóle nie zobaczą tego ruchu.

## 💻 Instrukcja użycia
Skrypt przyjmuje adres IP celu jako pierwszy i najważniejszy argument. Interfejs sieciowy podajemy za pomocą flagi -i.

```Bash
sudo ./pktgen_flood.sh <IP_CELU> -i <TWÓJ_INTERFEJS>
```
Przykład uruchomienia:
Jeżeli komputer, który chcesz przetestować, ma adres IP 192.168.1.100, a Twój lokalny interfejs sieciowy w laptopie to enp3s0:

```Bash
sudo ./pktgen_flood.sh 192.168.1.100 -i enp3s0
```
## 🛑 Zatrzymanie testu i wyniki
Skrypt działa w pętli nieskończonej. Aby przerwać generowanie ruchu, wciśnij kombinację klawiszy Ctrl + C.

Po zatrzymaniu, na ekranie automatycznie wyświetlą się statystyki wydajności dla każdego rdzenia procesora. Interesuje Cię parametr określający liczbę pakietów na sekundę (np. pps: 1488095). Zsumowanie wartości ze wszystkich rdzeni da Ci całkowity wygenerowany ruch z danej maszyny.