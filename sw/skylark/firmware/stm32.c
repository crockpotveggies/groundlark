/* SPDX-License-Identifier: GPL-3.0-only
 * Skylark Rev A, STM32F072CBT6. USB and peripheral registers via libopencm3.
 */
#include "platform.h"
#include "boot.h"
#include "peripherals.h"
#include <libopencm3/cm3/cortex.h>
#include <libopencm3/cm3/nvic.h>
#include <libopencm3/cm3/systick.h>
#include <libopencm3/stm32/rcc.h>
#include <libopencm3/stm32/crs.h>
#include <libopencm3/stm32/gpio.h>
#include <libopencm3/stm32/i2c.h>
#include <libopencm3/stm32/usart.h>
#include <libopencm3/stm32/adc.h>
#include <libopencm3/stm32/flash.h>
#include <libopencm3/stm32/iwdg.h>
#include <libopencm3/usb/usbd.h>
#include <libopencm3/usb/cdc.h>
#include <string.h>

/* pid.codes 1209:0001 is exclusively for private testing. Production builds
 * must override both IDs with an allocated pair. See README. */
#ifndef SK_USB_VID
#define SK_USB_VID 0x1209
#define SK_USB_PID 0x0001
#endif
static sk_state state;
static usbd_device *usb;
static volatile uint64_t milliseconds;
static bool configured,dtr,suspended;
static uint16_t tx_offset;
static bool tx_busy,zlp_pending,slow_clock;
static volatile uint8_t rx[256],rx_head,rx_tail;
static volatile bool rx_error;
/* Keep the polled USB peripheral above ES0223's 10 MHz APB minimum, even
 * while servicing resume/reset. APB is undivided relative to AHB here. */
#define SK_SUSPEND_HZ 12000000u
_Static_assert(SK_SUSPEND_HZ>=10000000u,"USB APB minimum");
_Static_assert(ADC_CR_ADEN==1 && ADC_CR_ADCAL==(1u<<31) && ADC_CR_ADSTP==16 &&
               ADC_ISR_EOC==4 && ADC_ISR_OVR==16 && I2C_ISR_BERR==256 &&
               I2C_ISR_NACKF==16 && I2C_ISR_ARLO==512,"MMIO fixture bit definitions");
uint32_t sk_register_read(sk_register reg) {
    switch(reg) {
    case SK_ADC_CR:return ADC_CR(ADC1);
    case SK_ADC_ISR:return ADC_ISR(ADC1);
    case SK_ADC_CHSELR:return ADC_CHSELR(ADC1);
    case SK_ADC_DR:return ADC_DR(ADC1);
    case SK_I2C_ISR:return I2C_ISR(I2C1);
    case SK_I2C_ICR:return 0;
    }return 0;
}
void sk_register_write(sk_register reg,uint32_t value) {
    switch(reg) {
    case SK_ADC_CR:ADC_CR(ADC1)=value;break;
    case SK_ADC_ISR:ADC_ISR(ADC1)=value;break;
    case SK_ADC_CHSELR:ADC_CHSELR(ADC1)=value;break;
    case SK_I2C_ICR:I2C_ICR(I2C1)=value;break;
    default:break;
    }
}
void sys_tick_handler(void) { milliseconds++; }
uint64_t sk_clock(void) { uint32_t mask=cm_mask_interrupts(1);uint64_t t=milliseconds;cm_mask_interrupts(mask);return t; }
static void service(void) {
    if(usb)usbd_poll(usb);
    if(rx_error) { rx_error=false;rx_tail=rx_head;sk_uart_error(); }
    for(unsigned n=0;n<64 && rx_tail!=rx_head;n++) { uint8_t b=rx[rx_tail++];sk_uart_input(b); }
}
void sk_delay(uint32_t ms) { uint64_t end=sk_clock()+ms;while(sk_clock()<end)service(); }
void sk_clamp(bool hold) { if(hold || !state.powered)gpio_set(GPIOB,GPIO13);else gpio_clear(GPIOB,GPIO13); }
static void pm_off(void) {
    gpio_clear(GPIOA,GPIO4);gpio_set(GPIOA,GPIO6|GPIO7);
    gpio_mode_setup(GPIOA,GPIO_MODE_INPUT,GPIO_PUPD_NONE,GPIO2);
}
void sk_rails(bool enabled) {
    if(enabled) {
        gpio_set(GPIOB,GPIO12|GPIO1);
        if(sk_pm_supply_ok()) {
            gpio_clear(GPIOA,GPIO6|GPIO7);gpio_set(GPIOA,GPIO4);
            gpio_mode_setup(GPIOA,GPIO_MODE_AF,GPIO_PUPD_NONE,GPIO2);
        }
    } else {
        /* Caller has already engaged WE/AE-to-RE clamps. */
        gpio_clear(GPIOB,GPIO1); /* Hold ADS122C04 reset before removing AVDD. */
        gpio_clear(GPIOB,GPIO12|GPIO3);pm_off();
    }
}
static bool i2c_wait(uint32_t flag,uint64_t end) {
    return sk_i2c_wait_flag(flag,end);
}
bool sk_i2c(uint8_t addr,const uint8_t *w,size_t wn,uint8_t *r,size_t rn) {
    if(wn>32 || rn>32 || (!wn && !rn))return false;
    uint64_t end=sk_clock()+5;bool ok=true;
    while(i2c_busy(I2C1))if(sk_clock()>=end) { ok=false;break; }
    I2C_ICR(I2C1)=0x3f38;
    if(ok && wn) {
        I2C_CR2(I2C1)=((uint32_t)addr<<1)|((uint32_t)wn<<16)|I2C_CR2_START|(rn?0:I2C_CR2_AUTOEND);
        for(size_t i=0;i<wn && ok;i++) { ok=i2c_wait(I2C_ISR_TXIS,end);if(ok)I2C_TXDR(I2C1)=w[i]; }
        if(ok)ok=i2c_wait(rn?I2C_ISR_TC:I2C_ISR_STOPF,end);
    }
    if(ok && rn) {
        I2C_CR2(I2C1)=((uint32_t)addr<<1)|((uint32_t)rn<<16)|I2C_CR2_RD_WRN|I2C_CR2_START|I2C_CR2_AUTOEND;
        for(size_t i=0;i<rn && ok;i++) { ok=i2c_wait(I2C_ISR_RXNE,end);if(ok)r[i]=(uint8_t)I2C_RXDR(I2C1); }
        if(ok)ok=i2c_wait(I2C_ISR_STOPF,end);
    }
    if(!ok) { I2C_CR2(I2C1)|=I2C_CR2_STOP;i2c_peripheral_disable(I2C1);i2c_peripheral_enable(I2C1); }
    I2C_ICR(I2C1)=0x3f38;return ok;
}
bool sk_pm_supply_ok(void) {
    unsigned raw=sk_adc_sample(0),ref=sk_adc_sample(17),cal=*(const uint16_t *)0x1ffff7ba;
    bool ok=ref && cal && gpio_get(GPIOA,GPIO5) && ((uint64_t)raw*6600*cal >= (uint64_t)4650*4095*ref);
    if(!ok)pm_off();
    return ok;
}
void usart2_isr(void) {
    uint32_t status=USART_ISR(USART2);
    if(status&(USART_ISR_ORE|USART_ISR_FE|USART_ISR_NF|USART_ISR_PE)) { USART_ICR(USART2)=15;rx_error=true; }
    if(status&USART_ISR_RXNE) {
        uint8_t b=(uint8_t)USART_RDR(USART2),next=(uint8_t)(rx_head+1);
        if(next==rx_tail)rx_error=true;else { rx[rx_head]=b;rx_head=next; }
    }
}
static const struct usb_device_descriptor device={
    .bLength=USB_DT_DEVICE_SIZE,.bDescriptorType=USB_DT_DEVICE,.bcdUSB=0x0200,
    .bDeviceClass=USB_CLASS_CDC,.bMaxPacketSize0=64,.idVendor=SK_USB_VID,
    .idProduct=SK_USB_PID,.bcdDevice=0x0100,.iManufacturer=1,.iProduct=2,.iSerialNumber=3,.bNumConfigurations=1};
static const struct usb_endpoint_descriptor comm_ep[]={
    {.bLength=USB_DT_ENDPOINT_SIZE,.bDescriptorType=USB_DT_ENDPOINT,.bEndpointAddress=0x83,.bmAttributes=USB_ENDPOINT_ATTR_INTERRUPT,.wMaxPacketSize=16,.bInterval=255}};
static const struct usb_endpoint_descriptor data_ep[]={
    {.bLength=USB_DT_ENDPOINT_SIZE,.bDescriptorType=USB_DT_ENDPOINT,.bEndpointAddress=0x01,.bmAttributes=USB_ENDPOINT_ATTR_BULK,.wMaxPacketSize=64},
    {.bLength=USB_DT_ENDPOINT_SIZE,.bDescriptorType=USB_DT_ENDPOINT,.bEndpointAddress=0x82,.bmAttributes=USB_ENDPOINT_ATTR_BULK,.wMaxPacketSize=64}};
static const struct {
    struct usb_cdc_header_descriptor header;
    struct usb_cdc_call_management_descriptor call;
    struct usb_cdc_acm_descriptor acm;
    struct usb_cdc_union_descriptor group;
} __attribute__((packed)) extra={
    {5,CS_INTERFACE,USB_CDC_TYPE_HEADER,0x0110},
    {5,CS_INTERFACE,USB_CDC_TYPE_CALL_MANAGEMENT,0,1},
    {4,CS_INTERFACE,USB_CDC_TYPE_ACM,2},
    {5,CS_INTERFACE,USB_CDC_TYPE_UNION,0,1}};
static const struct usb_interface_descriptor interfaces[]={
    {.bLength=USB_DT_INTERFACE_SIZE,.bDescriptorType=USB_DT_INTERFACE,.bInterfaceNumber=0,.bNumEndpoints=1,.bInterfaceClass=USB_CLASS_CDC,.bInterfaceSubClass=USB_CDC_SUBCLASS_ACM,.bInterfaceProtocol=USB_CDC_PROTOCOL_AT,.endpoint=comm_ep,.extra=&extra,.extralen=sizeof extra},
    {.bLength=USB_DT_INTERFACE_SIZE,.bDescriptorType=USB_DT_INTERFACE,.bInterfaceNumber=1,.bNumEndpoints=2,.bInterfaceClass=USB_CLASS_DATA,.endpoint=data_ep}};
static const struct usb_interface ifaces[]={{.num_altsetting=1,.altsetting=interfaces},{.num_altsetting=1,.altsetting=interfaces+1}};
static const struct usb_config_descriptor configuration={
    .bLength=USB_DT_CONFIGURATION_SIZE,.bDescriptorType=USB_DT_CONFIGURATION,.bNumInterfaces=2,.bConfigurationValue=1,.bmAttributes=0x80,.bMaxPower=250,.interface=ifaces};
static uint8_t control_buffer[128];
static struct usb_cdc_line_coding coding={115200,0,0,8};
static enum usbd_request_return_codes control(usbd_device *dev,struct usb_setup_data *req,uint8_t **buf,uint16_t *len,void (**complete)(usbd_device *,struct usb_setup_data *)) {
    (void)dev;(void)complete;
    if(req->wIndex!=0)return USBD_REQ_NOTSUPP;
    if(req->bRequest==USB_CDC_REQ_SET_CONTROL_LINE_STATE) { dtr=(req->wValue&1)!=0;return USBD_REQ_HANDLED; }
    if(req->bRequest==USB_CDC_REQ_GET_LINE_CODING) { *buf=(uint8_t *)&coding;*len=sizeof coding;return USBD_REQ_HANDLED; }
    if(req->bRequest==USB_CDC_REQ_SET_LINE_CODING && *len==sizeof coding) { memcpy(&coding,*buf,sizeof coding);return USBD_REQ_HANDLED; }
    return USBD_REQ_NOTSUPP;
}
static void receive(usbd_device *dev,uint8_t ep) { uint8_t ignored[64];usbd_ep_read_packet(dev,ep,ignored,sizeof ignored); }
static void transmitted(usbd_device *dev,uint8_t ep) { (void)dev;(void)ep;tx_busy=false; }
static void set_config(usbd_device *dev,uint16_t value) {
    configured=value==1;
    if(!configured)return;
    usbd_ep_setup(dev,0x01,USB_ENDPOINT_ATTR_BULK,64,receive);
    tx_busy=false;zlp_pending=false;
    usbd_ep_setup(dev,0x82,USB_ENDPOINT_ATTR_BULK,64,transmitted);
    usbd_ep_setup(dev,0x83,USB_ENDPOINT_ATTR_INTERRUPT,16,NULL);
    usbd_register_control_callback(dev,USB_REQ_TYPE_CLASS|USB_REQ_TYPE_INTERFACE,USB_REQ_TYPE_TYPE|USB_REQ_TYPE_RECIPIENT,control);
}
static void reset_usb(void) { configured=false;dtr=false;suspended=false;tx_busy=false;zlp_pending=false;tx_offset=0;sk_supply(&state,false,sk_clock()); }
static void suspend_usb(void) { suspended=true;tx_offset=0;sk_supply(&state,false,sk_clock()); }
static void resume_usb(void) { suspended=false; }
static void power_clock(void) {
    if(suspended==slow_clock)return;
    if(suspended) {
        (void)sk_adc_disable();
        usart_disable(USART2);i2c_peripheral_disable(I2C1);
        rcc_set_hpre(RCC_CFGR_HPRE_DIV4);systick_set_reload(SK_SUSPEND_HZ/1000-1);
    } else {
        rcc_set_hpre(RCC_CFGR_HPRE_NODIV);systick_set_reload(47999);
        (void)sk_adc_enable();
        i2c_peripheral_enable(I2C1);usart_enable(USART2);
    }
    slow_clock=suspended;
}
static void boot_erase(unsigned page) { flash_erase_page(0x0801f000+page*2048); }
static void boot_program(unsigned word,uint32_t value) { flash_program_word(0x0801f000+word*4,value); }
static uint64_t boot_identity(void) {
    flash_unlock();flash_clear_status_flags();
    uint32_t id=sk_boot_next((const volatile uint32_t *)0x0801f000,boot_erase,boot_program);
    flash_lock();return id;
}
int main(void) {
    rcc_clock_setup_in_hsi48_out_48mhz();rcc_set_usbclk_source(RCC_HSI48);
    rcc_periph_clock_enable(RCC_GPIOA);rcc_periph_clock_enable(RCC_GPIOB);
    /* Deliberate NCs from the 48-pin board pin audit: disable floating input
     * buffers. Keep SWD, USB, boot, reset and connected sensor pins intact. */
    rcc_periph_clock_enable(RCC_GPIOC);rcc_periph_clock_enable(RCC_GPIOF);
    gpio_mode_setup(GPIOA,GPIO_MODE_ANALOG,GPIO_PUPD_NONE,GPIO1|GPIO8|GPIO9|GPIO10|GPIO15);
    gpio_mode_setup(GPIOB,GPIO_MODE_ANALOG,GPIO_PUPD_NONE,GPIO2|GPIO4|GPIO5|GPIO8|GPIO9|GPIO10|GPIO11|GPIO14|GPIO15);
    gpio_mode_setup(GPIOC,GPIO_MODE_ANALOG,GPIO_PUPD_NONE,GPIO13|GPIO14|GPIO15);
    gpio_mode_setup(GPIOF,GPIO_MODE_ANALOG,GPIO_PUPD_NONE,GPIO0|GPIO1);
    gpio_set(GPIOB,GPIO13);gpio_clear(GPIOB,GPIO12|GPIO3|GPIO1);
    gpio_mode_setup(GPIOB,GPIO_MODE_OUTPUT,GPIO_PUPD_NONE,GPIO13|GPIO12|GPIO1|GPIO3);
    gpio_clear(GPIOA,GPIO4);gpio_set(GPIOA,GPIO6|GPIO7);
    gpio_mode_setup(GPIOA,GPIO_MODE_OUTPUT,GPIO_PUPD_NONE,GPIO4|GPIO6|GPIO7);
    gpio_mode_setup(GPIOA,GPIO_MODE_INPUT,GPIO_PUPD_NONE,GPIO5);
    systick_set_clocksource(STK_CSR_CLKSOURCE_AHB);systick_set_reload(47999);systick_interrupt_enable();systick_counter_enable();
    rcc_periph_clock_enable(RCC_I2C1);rcc_set_i2c_clock_hsi(RCC_I2C1);
    rcc_osc_on(RCC_HSI);rcc_wait_for_osc_ready(RCC_HSI);
    gpio_mode_setup(GPIOB,GPIO_MODE_AF,GPIO_PUPD_NONE,GPIO6|GPIO7);gpio_set_af(GPIOB,GPIO_AF1,GPIO6|GPIO7);
    gpio_set_output_options(GPIOB,GPIO_OTYPE_OD,GPIO_OSPEED_2MHZ,GPIO6|GPIO7);
    i2c_set_speed(I2C1,i2c_speed_sm_100k,8);i2c_peripheral_enable(I2C1);
    rcc_periph_clock_enable(RCC_USART2);gpio_set_af(GPIOA,GPIO_AF1,GPIO2|GPIO3);
    gpio_mode_setup(GPIOA,GPIO_MODE_AF,GPIO_PUPD_NONE,GPIO3);
    usart_set_baudrate(USART2,9600);usart_set_databits(USART2,8);usart_set_stopbits(USART2,USART_STOPBITS_1);
    usart_set_parity(USART2,USART_PARITY_NONE);usart_set_mode(USART2,USART_MODE_TX_RX);usart_set_flow_control(USART2,USART_FLOWCONTROL_NONE);
    usart_enable_rx_interrupt(USART2);nvic_enable_irq(NVIC_USART2_IRQ);usart_enable(USART2);
    rcc_periph_clock_enable(RCC_ADC);gpio_mode_setup(GPIOA,GPIO_MODE_ANALOG,GPIO_PUPD_NONE,GPIO0);
    ADC_CCR(ADC1)|=ADC_CCR_VREFEN;ADC_SMPR(ADC1)=7;
    (void)sk_adc_initialize(); /* Failure disables PMS power, not the USB host. */
    char serial[25];static const char hex[]="0123456789abcdef";
    const uint8_t *uid=(const uint8_t *)0x1ffff7ac;
    for(unsigned i=0;i<12;i++) { serial[2*i]=hex[uid[i]>>4];serial[2*i+1]=hex[uid[i]&15]; }serial[24]=0;
    sk_init(&state,serial,boot_identity());
    const char *strings[]={"Groundlark","Skylark USB prototype",serial};
    rcc_periph_clock_enable(RCC_CRS);crs_autotrim_usb_enable();rcc_periph_clock_enable(RCC_USB);
    gpio_mode_setup(GPIOA,GPIO_MODE_AF,GPIO_PUPD_NONE,GPIO11|GPIO12);gpio_set_af(GPIOA,GPIO_AF2,GPIO11|GPIO12);
    usb=usbd_init(&st_usbfs_v2_usb_driver,&device,&configuration,strings,3,control_buffer,sizeof control_buffer);
    usbd_register_set_config_callback(usb,set_config);usbd_register_reset_callback(usb,reset_usb);
    usbd_register_suspend_callback(usb,suspend_usb);usbd_register_resume_callback(usb,resume_usb);
    iwdg_set_period_ms(2000);iwdg_start();
    for(;;) {
        service();power_clock();bool available=configured && !suspended;
        sk_supply(&state,available,sk_clock());
        bool connected=available && dtr;
        if(connected!=state.connected) { tx_offset=0;sk_connection(&state,connected,sk_clock()); }
        sk_tick(&state,sk_clock());
        uint16_t len;const uint8_t *frame=sk_tx(&state,&len);
        if(connected && !tx_busy && zlp_pending) {
            tx_busy=true;zlp_pending=false;usbd_ep_write_packet(usb,0x82,NULL,0);
        } else if(frame && connected && !tx_busy) {
            unsigned remain=len-tx_offset,n=remain>64?64:remain;
            int sent=usbd_ep_write_packet(usb,0x82,frame+tx_offset,n);
            if(sent>0) { tx_busy=true;tx_offset+=(uint16_t)sent;if(tx_offset==len) { sk_tx_done(&state);tx_offset=0;zlp_pending=sent==64; } }
        }
        iwdg_reset();__asm__("wfi");
    }
}
