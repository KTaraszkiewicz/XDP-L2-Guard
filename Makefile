DATA_PLANE_DIR = src/data_plane

# Dynamiczne pobranie ścieżki multiarch (dla Ubuntu/Debian, np. x86_64-linux-gnu)
MULTIARCH := $(shell gcc -print-multiarch)

all: $(DATA_PLANE_DIR)/filter.o

$(DATA_PLANE_DIR)/filter.o: $(DATA_PLANE_DIR)/filter.c
	@echo "🛠️  Kompilacja AOT (CO-RE) dla XDP Data Plane..."
	clang -O2 -g -Wall -target bpf \
		-D__TARGET_ARCH_x86 \
		-I/usr/include/$(MULTIARCH) \
		-c $< -o $@
	@echo "✅ Pomyślnie wygenerowano obiekt BPF: $@"

clean:
	rm -f $(DATA_PLANE_DIR)/filter.o