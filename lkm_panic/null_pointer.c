#include <linux/module.h>
#include <linux/kernel.h>

MODULE_LICENSE("GPL");
MODULE_AUTHOR("Systems Engineer");
MODULE_DESCRIPTION("Kernel Panic Demonstration (NULL Pointer Dereference)");

int init_module(void) {
    int *ptr = NULL;
    printk(KERN_EMERG "LKM: Initializing destructive module...\n");
    printk(KERN_EMERG "LKM: Attempting to write to NULL address (0x0)...\n");
    
    // The catastrophe happens here:
    *ptr = 42; 
    
    return 0;
}

void cleanup_module(void) {
    printk(KERN_INFO "LKM: Module removed.\n");
}