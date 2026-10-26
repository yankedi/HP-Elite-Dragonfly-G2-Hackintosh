/* SPDX-License-Identifier: MIT */
#include "identity.h"

#include <string.h>

enum nmx_personality
nmx_pci_personality(const drmDevicePtr device)
{
   if (device == NULL || device->bustype != DRM_BUS_PCI ||
       device->deviceinfo.pci == NULL)
      return NMX_PERSONALITY_UNKNOWN;

   switch (device->deviceinfo.pci->vendor_id) {
   case 0x8086:
      return NMX_PERSONALITY_INTEL;
   case 0x1002:
      return NMX_PERSONALITY_AMD;
   default:
      return NMX_PERSONALITY_UNKNOWN;
   }
}

int
nmx_pci_identity_equal(const drmDevicePtr a, const drmDevicePtr b)
{
   if (a == NULL || b == NULL || a->bustype != DRM_BUS_PCI ||
       b->bustype != DRM_BUS_PCI || a->businfo.pci == NULL ||
       b->businfo.pci == NULL)
      return 0;

   return a->businfo.pci->domain == b->businfo.pci->domain &&
          a->businfo.pci->bus == b->businfo.pci->bus &&
          a->businfo.pci->dev == b->businfo.pci->dev &&
          a->businfo.pci->func == b->businfo.pci->func;
}

const char *
nmx_personality_name(enum nmx_personality personality)
{
   switch (personality) {
   case NMX_PERSONALITY_INTEL:
      return "intel";
   case NMX_PERSONALITY_AMD:
      return "amd";
   default:
      return "unknown";
   }
}
