# DAQHAT-01 Pi power supervisor

`firmware/` targets MSPM0L1106TRHBR. The default image leaves RUN off because
the battery/controller policy is disabled. JP130 remains a bench override;
automatic operation requires removing its shunt. Coldfoot is outside this target.

The production C state machine checks voltage hysteresis, confirmation intervals,
minimum off time and halt acknowledgement. Invalid ADC readings request orderly
shutdown while running and prevent restart while off. Three shutdown timeouts
latch the controller off until reset. An independent watchdog resets a stalled
firmware loop. MCU reset returns RUN to its externally pulled-down state.

PA3 drives RUN, PA4 requests shutdown through Q130, PA5 reads ACK_N through Q131,
and PA27/ADC0.0 measures the R135/R136 divider. The nominal 2.5 V ADC conversion
is not calibrated. SWD remains available. The default image does not write factory
BCR/BSL configuration memory or provision a battery policy.

Build and native fault tests run in `./lab.ps1 test -Profile software`.
The TI SDK is pinned by `environment/install_supervisor.py`; its BSD notices
remain in the toolchain sources. Target linking and native tests are software
evidence only. ADC accuracy, voltage transients, watchdog timing and shutdown
behavior require the actual board.

For a later supervised bench build, start from
`sw/pi/deploy/power-policy.example.json`, select the protected battery/controller,
then generate a separate policy header:

```sh
python sw/supervisor/configure.py selected-policy.json /tmp/selected-policy.h
make -C sw/supervisor/firmware EXTRA_CFLAGS='-DPOLICY_HEADER=\"/tmp/selected-policy.h\"'
```

Every enabled policy must pass both the Python and C validators. Selecting a policy
does not qualify it. Flash over SWD only during physical bring-up.

Pi handshake settings are in `sw/pi/deploy/supervisor-boot.cfg`. BCM6 generates
a power-key shutdown request; BCM13 is asserted by the kernel poweroff path,
after filesystem shutdown. A stopped acquisition service never asserts halt.
Install the logind drop-in during that bring-up. The `gpio-poweroff` overlay
requires working external power removal; do not enable it with the default
disabled supervisor image or with JP130 bypassing the switch.
