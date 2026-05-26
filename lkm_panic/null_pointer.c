#include <linux/module.h>
#include <linux/kernel.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Inzynier Systemowy");
MODULE_DESCRIPTION("Prezentacja bledu Kernel Panic (Dereferencja NULL)");

int init_module(void) {
    int *ptr = NULL;
    printk(KERN_EMERG "LKM: Inicjalizacja destrukcyjnego modulu...\n");
    printk(KERN_EMERG "LKM: Proba zapisu do adresu NULL (0x0)...\n");
    
    // Katastrofa następuje tutaj:
    *ptr = 42; 
    
    return 0;
}

void cleanup_module(void) {
    printk(KERN_INFO "LKM: Modul usuniety.\n");
}