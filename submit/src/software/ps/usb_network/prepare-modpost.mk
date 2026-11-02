# Supplement the original kernel Makefile only for this explicit host-tool target.
.PHONY: ss-usb-modpost
ss-usb-modpost:
	$(MAKE) $(build)=scripts/mod __build
