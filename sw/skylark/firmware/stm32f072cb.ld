/* Last 4 KiB reserved for the boot-identity journal. */
MEMORY {
  rom (rx) : ORIGIN = 0x08000000, LENGTH = 124K
  ram (rwx) : ORIGIN = 0x20000000, LENGTH = 16K
}
INCLUDE cortex-m-generic.ld
ASSERT(_ebss <= ORIGIN(ram) + LENGTH(ram) - 4096, "Reserve at least 4 KiB stack")
