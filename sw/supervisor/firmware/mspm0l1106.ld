ENTRY(start)
MEMORY { FLASH (rx) : ORIGIN = 0, LENGTH = 64K
         RAM (rwx) : ORIGIN = 0x20000000, LENGTH = 4K }
_stack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS {
 .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) } > FLASH
 .data : { _sdata = .; *(.data*) _edata = .; } > RAM AT> FLASH
 _sidata = LOADADDR(.data);
 .bss (NOLOAD) : { _sbss = .; *(.bss*) *(COMMON) _ebss = .; } > RAM
 /DISCARD/ : { *(.comment*) *(.ARM.exidx*) *(.ARM.extab*) }
 ASSERT(_ebss <= _stack - 2048, "2 KiB stack reserve")
}
