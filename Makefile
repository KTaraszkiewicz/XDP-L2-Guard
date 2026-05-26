DATA_PLANE_DIR = src/data_plane

all: $(DATA_PLANE_DIR)/filter.o

$(DATA_PLANE_DIR)/filter.o: $(DATA_PLANE_DIR)/filter.c
	@echo "🛠️  Kompilacja AOT (CO-RE) dla XDP Data Plane..."
	clang -O2 -g -Wall -target bpf -D__TARGET_ARCH_x86 -c $< -o $@
	@echo "✅ Pomyślnie wygenerowano obiekt BPF: $@"

clean:
	rm -f $(DATA_PLANE_DIR)/filter.o