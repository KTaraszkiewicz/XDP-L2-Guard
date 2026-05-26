DATA_PLANE_DIR = src/data_plane

# Dynamically fetch the multiarch path (for Ubuntu/Debian, e.g., x86_64-linux-gnu)
MULTIARCH := $(shell gcc -print-multiarch)

all: $(DATA_PLANE_DIR)/filter.o

$(DATA_PLANE_DIR)/filter.o: $(DATA_PLANE_DIR)/filter.c
	@echo "🛠️  Compiling AOT (CO-RE) for XDP Data Plane..."
	clang -O2 -g -Wall -target bpf \
		-D__TARGET_ARCH_x86 \
		-I/usr/include/$(MULTIARCH) \
		-c $< -o $@
	@echo "✅ Successfully generated BPF object: $@"

clean:
	rm -f $(DATA_PLANE_DIR)/filter.o