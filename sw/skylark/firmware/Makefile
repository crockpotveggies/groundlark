ROOT := ../../..
LIBOPENCM3 ?= $(ROOT)/.local/skylark-fw/libopencm3
PREFIX ?= arm-none-eabi-
BUILD ?= ../build
CC := $(PREFIX)gcc
CFLAGS := -std=c11 -Os -g3 -Wall -Wextra -Werror -ffunction-sections -fdata-sections -fno-builtin -fstack-usage -mcpu=cortex-m0 -mthumb -msoft-float -DSTM32F0 -I$(LIBOPENCM3)/include $(EXTRA_CFLAGS)
SOURCES := core.c sensors.c boot.c peripherals.c stm32.c memory.c
OBJECTS := $(addprefix $(BUILD)/,$(SOURCES:.c=.o))
.PHONY: all
all: $(BUILD)/skylark.elf $(BUILD)/skylark.bin
$(BUILD):
	mkdir -p $@
$(BUILD)/%.o: %.c skylark.h platform.h boot.h peripherals.h | $(BUILD)
	$(CC) $(CFLAGS) -c $< -o $@
$(BUILD)/skylark.elf: $(OBJECTS) stm32f072cb.ld
	$(CC) $(CFLAGS) -nostdlib -L$(LIBOPENCM3)/lib -Tstm32f072cb.ld -Wl,--gc-sections,-Map,$(BUILD)/skylark.map $(OBJECTS) -lopencm3_stm32f0 -lgcc -o $@
	$(PREFIX)size $@
$(BUILD)/skylark.bin: $(BUILD)/skylark.elf
	$(PREFIX)objcopy -O binary $< $@
