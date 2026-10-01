SDK ?= /opt/supervisor/mspm0-sdk
BUILD ?= ../build
CC = arm-none-eabi-gcc
CFLAGS = -std=c11 -Os -g -Wall -Wextra -Werror -fno-builtin -mcpu=cortex-m0plus -mthumb -ffunction-sections -fdata-sections -D__MSPM0L1106__ -I$(SDK)/source -I$(SDK)/source/third_party/CMSIS/Core/Include -isystem/usr/include/newlib $(EXTRA_CFLAGS)
SOURCES = mspm0.c power.c ../../skylark/firmware/memory.c $(SDK)/source/ti/driverlib/dl_adc12.c $(SDK)/source/ti/driverlib/dl_vref.c
all: $(BUILD)/supervisor.bin
$(BUILD)/supervisor.elf: $(SOURCES) power.h policy.h mspm0l1106.ld
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(SOURCES) -nostdlib -Wl,--gc-sections,-Map,$(BUILD)/supervisor.map -Tmspm0l1106.ld -lgcc -o $@
	arm-none-eabi-size $@
$(BUILD)/supervisor.bin: $(BUILD)/supervisor.elf
	arm-none-eabi-objcopy -O binary $< $@
.PHONY: all
