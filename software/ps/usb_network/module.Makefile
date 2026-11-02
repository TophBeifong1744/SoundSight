# Wrapper only; vendor C/header sources are kept unmodified.
obj-m += u_ether.o usb_f_rndis.o
usb_f_rndis-y := f_rndis.o rndis.o
ccflags-y += -I$(src)/..
