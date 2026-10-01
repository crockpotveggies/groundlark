LIBOPENCM3 ?= ../../../.local/skylark-fw/libopencm3
BUILD ?= ../build
CC := arm-none-eabi-gcc
SHARED := ../../skylark/firmware
CFLAGS := -std=c11 -Os -g -Wall -Wextra -Werror -Wno-misleading-indentation -ffunction-sections -fdata-sections -fno-builtin -mcpu=cortex-m0 -mthumb -msoft-float -DSTM32F0 -DBOOT_PAGE_WORDS=256 -I$(LIBOPENCM3)/include -I$(SHARED) $(EXTRA_CFLAGS)
all: $(BUILD)/burrowlark.elf $(BUILD)/burrowlark.bin
$(BUILD):
	mkdir -p $@
$(BUILD)/burrowlark.elf: head.c head.h stm32.c stm32f042k6.ld $(SHARED)/boot.c $(SHARED)/memory.c | $(BUILD)
	$(CC) $(CFLAGS) -nostdlib -L$(LIBOPENCM3)/lib -Tstm32f042k6.ld -Wl,--gc-sections,-Map,$(BUILD)/burrowlark.map head.c stm32.c $(SHARED)/boot.c $(SHARED)/memory.c -lopencm3_stm32f0 -lgcc -o $@
	arm-none-eabi-size $@
$(BUILD)/burrowlark.bin: $(BUILD)/burrowlark.elf
	arm-none-eabi-objcopy -O binary $< $@
