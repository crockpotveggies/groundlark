/* Last two 1 KiB flash pages hold boot identity. */
MEMORY {
  rom (rx) : ORIGIN = 0x08000000, LENGTH = 30K
  ram (rwx) : ORIGIN = 0x20000000, LENGTH = 6K
}
INCLUDE cortex-m-generic.ld
ASSERT(_ebss <= ORIGIN(ram) + LENGTH(ram) - 2048, "Reserve 2 KiB stack")
